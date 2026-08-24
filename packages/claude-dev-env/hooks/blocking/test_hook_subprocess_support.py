"""Shared subprocess support for blocking-hook behavior tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

HOOK_SUBPROCESS_TIMEOUT_SECONDS: int = 10


def run_hook_as_subprocess(
    hook_script_path: str | Path,
    payload_text: str,
    working_directory: str | Path,
    home_directory: str | Path,
    *,
    all_environment_names_to_remove: tuple[str, ...] = (),
    environment_updates_by_name: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a hook through its real ``__main__`` path with captured text streams."""
    resolved_hook_script_path = Path(hook_script_path).resolve()
    environment_update_by_name = environment_updates_by_name or {}
    all_environment_names_to_exclude = {
        _environment_name_comparison_key(each_environment_name)
        for each_environment_name in (
            *all_environment_names_to_remove,
            *environment_update_by_name,
        )
    }
    environment_variable_by_name = {
        each_environment_name: each_environment_value
        for each_environment_name, each_environment_value in os.environ.items()
        if _environment_name_comparison_key(each_environment_name)
        not in all_environment_names_to_exclude
    }
    environment_variable_by_name.update(environment_update_by_name)
    resolved_home_directory = Path(home_directory).resolve()
    for each_environment_name in ("HOME", "USERPROFILE", "TEMP", "TMP", "TMPDIR"):
        environment_variable_by_name[each_environment_name] = str(resolved_home_directory)
    environment_variable_by_name["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(resolved_hook_script_path)],
        input=payload_text,
        cwd=working_directory,
        env=environment_variable_by_name,
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=HOOK_SUBPROCESS_TIMEOUT_SECONDS,
    )


def build_bash_payload(command: str, *, tool_input_cwd: str | Path | None = None) -> str:
    """Build the serialized Bash tool payload for a command."""
    command_field_by_name = {"command": command}
    if tool_input_cwd is not None:
        command_field_by_name["cwd"] = str(tool_input_cwd)
    return json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": command_field_by_name,
        }
    )


def _environment_name_comparison_key(environment_name: str) -> str:
    if os.name == "nt":
        return environment_name.casefold()
    return environment_name


def assert_hook_deny_log_contains(
    home_directory: str | Path, hook_filename: str
) -> None:
    """Assert that the isolated hook-block log records the named hook."""
    deny_log_path = Path(home_directory) / ".claude" / "logs" / "hook-blocks.log"
    assert deny_log_path.is_file(), f"Missing deny log: {deny_log_path}"
    deny_log_text = deny_log_path.read_text(encoding="utf-8")
    assert hook_filename in deny_log_text, (
        f"Missing {hook_filename} in deny log: {deny_log_text}"
    )


def test_run_hook_as_subprocess_resolves_relative_path_and_isolates_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    absolute_hook_script_path = (
        Path(__file__).resolve().parent / "open_questions_in_plans_blocker.py"
    )
    monkeypatch.chdir(absolute_hook_script_path.parent)
    relative_hook_script_path = Path(absolute_hook_script_path.name)
    isolated_home_directory = tmp_path / "isolated-home"
    isolated_home_directory.mkdir()
    plan_path = tmp_path / "docs" / "plans" / "feature.md"
    payload_text = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(plan_path),
                "content": "# Feature Plan\n\n## Open Questions\n\n- Choose a value.\n",
            },
        }
    )

    completed = run_hook_as_subprocess(
        hook_script_path=relative_hook_script_path,
        payload_text=payload_text,
        working_directory=tmp_path,
        home_directory=isolated_home_directory,
    )

    parsed_stdout = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stderr
    assert parsed_stdout["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert_hook_deny_log_contains(
        isolated_home_directory, "open_questions_in_plans_blocker.py"
    )


def test_run_hook_as_subprocess_returns_nonzero_probe_streams(
    tmp_path: Path,
) -> None:
    probe_script_path = tmp_path / "probe.py"
    probe_script_path.write_text(
        "import sys\n"
        "sys.stdout.write('probe stdout\\n')\n"
        "sys.stderr.write('probe stderr\\n')\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )

    completed = run_hook_as_subprocess(
        hook_script_path=probe_script_path,
        payload_text="",
        working_directory=tmp_path,
        home_directory=tmp_path / "isolated-home",
    )

    assert completed.returncode == 7, completed.stderr
    assert completed.stdout == "probe stdout\n"
    assert completed.stderr == "probe stderr\n"


def test_build_bash_payload_omits_optional_cwd() -> None:
    payload_text = build_bash_payload("rm -rf /tmp/example")

    assert json.loads(payload_text) == {
        "tool_name": "Bash",
        "tool_input": {
            "command": "rm -rf /tmp/example",
        },
    }


def test_build_bash_payload_includes_optional_cwd() -> None:
    payload_text = build_bash_payload(
        "rm -rf /tmp/example", tool_input_cwd="/tmp/work"
    )

    assert json.loads(payload_text) == {
        "tool_name": "Bash",
        "tool_input": {
            "command": "rm -rf /tmp/example",
            "cwd": "/tmp/work",
        },
    }


def test_run_hook_as_subprocess_handles_unicode_stdin_as_utf8(
    tmp_path: Path,
) -> None:
    probe_script_path = tmp_path / "probe.py"
    probe_script_path.write_text(
        "import sys\n"
        "sys.stdout.write(','.join(str(ord(each_character)) for each_character in sys.stdin.read()))\n",
        encoding="utf-8",
    )
    unicode_payload = "café 日本語"

    completed = run_hook_as_subprocess(
        hook_script_path=probe_script_path,
        payload_text=unicode_payload,
        working_directory=tmp_path,
        home_directory=tmp_path / "isolated-home",
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "99,97,102,233,32,26085,26412,35486"


def test_run_hook_as_subprocess_preserves_posix_mixed_case_environment_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_script_path = tmp_path / "probe.py"
    probe_script_path.write_text(
        "import json\n"
        "import os\n"
        "print(json.dumps(sorted((each_name, each_value) for each_name, each_value in os.environ.items() if each_name.casefold() == 'casesensitiveprobe')))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CaseSensitiveProbe", "before")

    completed = run_hook_as_subprocess(
        hook_script_path=probe_script_path,
        payload_text="",
        working_directory=tmp_path,
        home_directory=tmp_path / "isolated-home",
        environment_updates_by_name={"CASESENSITIVEPROBE": "after"},
    )

    child_environment_variable_by_name = json.loads(completed.stdout)
    if os.name == "nt":
        assert child_environment_variable_by_name == [["CASESENSITIVEPROBE", "after"]]
    else:
        assert child_environment_variable_by_name == [
            ["CASESENSITIVEPROBE", "after"],
            ["CaseSensitiveProbe", "before"],
        ]


def test_run_hook_as_subprocess_handles_windows_mixed_case_environment_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_script_path = tmp_path / "probe.py"
    probe_script_path.write_text(
        "import json\n"
        "import os\n"
        "print(json.dumps(sorted((each_name, each_value) for each_name, each_value in os.environ.items() if each_name.casefold() == 'casesensitiveprobe')))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CaseSensitiveProbe", "before")

    completed = run_hook_as_subprocess(
        hook_script_path=probe_script_path,
        payload_text="",
        working_directory=tmp_path,
        home_directory=tmp_path / "isolated-home",
        all_environment_names_to_remove=("casesensitiveprobe",),
        environment_updates_by_name={"CASESENSITIVEPROBE": "after"},
    )

    child_environment_variable_by_name = json.loads(completed.stdout)
    if os.name == "nt":
        assert child_environment_variable_by_name == [["CASESENSITIVEPROBE", "after"]]
    else:
        assert child_environment_variable_by_name == [
            ["CASESENSITIVEPROBE", "after"],
            ["CaseSensitiveProbe", "before"],
        ]


def test_run_hook_as_subprocess_keeps_default_home_and_temp_isolation(
    tmp_path: Path,
) -> None:
    probe_script_path = tmp_path / "probe.py"
    probe_script_path.write_text(
        "import json\n"
        "import os\n"
        "print(json.dumps({each_name: os.environ.get(each_name) for each_name in (\n"
        "    'HOME', 'USERPROFILE', 'TEMP', 'TMP', 'TMPDIR'\n"
        ")}))\n",
        encoding="utf-8",
    )
    isolated_home_directory = tmp_path / "isolated-home"
    isolated_home_directory.mkdir()

    completed = run_hook_as_subprocess(
        hook_script_path=probe_script_path,
        payload_text="",
        working_directory=tmp_path,
        home_directory=isolated_home_directory,
    )

    child_environment_variable_by_name = json.loads(completed.stdout)
    expected_home = str(isolated_home_directory.resolve())
    assert set(child_environment_variable_by_name.values()) == {expected_home}
