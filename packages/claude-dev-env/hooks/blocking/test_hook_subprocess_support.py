"""Shared subprocess support for blocking-hook behavior tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_SUBPROCESS_TIMEOUT_SECONDS: int = 10


def run_hook_as_subprocess(
    hook_script_path: str | Path,
    payload_text: str,
    working_directory: str | Path,
    home_directory: str | Path,
) -> subprocess.CompletedProcess[str]:
    """Run a hook through its real ``__main__`` path with captured text streams."""
    resolved_hook_script_path = Path(hook_script_path).resolve()
    resolved_home_directory = Path(home_directory).resolve()
    all_environment_variables = os.environ.copy()
    all_environment_variables["HOME"] = str(resolved_home_directory)
    all_environment_variables["USERPROFILE"] = str(resolved_home_directory)
    all_environment_variables["TEMP"] = str(resolved_home_directory)
    all_environment_variables["TMP"] = str(resolved_home_directory)
    all_environment_variables["TMPDIR"] = str(resolved_home_directory)
    return subprocess.run(
        [sys.executable, str(resolved_hook_script_path)],
        input=payload_text,
        cwd=working_directory,
        env=all_environment_variables,
        capture_output=True,
        text=True,
        check=False,
        timeout=HOOK_SUBPROCESS_TIMEOUT_SECONDS,
    )


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
