"""Ephemeral-path exemption tests for code_rules_enforcer and the classifier."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_enforcer import main as enforcer_main  # noqa: E402
from code_rules_shared import is_ephemeral_script_path  # noqa: E402

_ENFORCER_SCRIPT = Path(__file__).resolve().parent / "code_rules_enforcer.py"
_TDD_SCRIPT = Path(__file__).resolve().parent / "tdd_enforcer.py"

_VIOLATING_PRODUCTION_SOURCE = "def process_data(payload: str) -> None:\n    print(payload)\n"

code_rules_enforcer_module = SimpleNamespace(main=enforcer_main, sys=sys)


def _run_enforcer_cli(
    all_cli_arguments: list[str],
    extra_env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Drive the enforcer script through its real argv entry point.

    Args:
        all_cli_arguments: The argument vector appended after the script path.
        extra_env: Additional environment variables merged into the subprocess env.

    Returns:
        The completed process carrying stdout, stderr, and the exit code.
    """
    subprocess_env = {**os.environ, **extra_env}
    return subprocess.run(
        [sys.executable, str(_ENFORCER_SCRIPT), *all_cli_arguments],
        input="",
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_env,
    )


def _run_main_with_write_payload(
    file_path: str,
    content: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[str, int]:
    """Drive enforcer_main through its stdin entry point for a Write payload.

    Args:
        file_path: The destination path the Write targets.
        content: The content of the Write.
        monkeypatch: The pytest fixture used to redirect sys.stdin.
        capsys: The pytest fixture used to capture the deny payload on stdout.

    Returns:
        A tuple of (captured_stdout, exit_code).
    """
    write_payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
        }
    )
    monkeypatch.setattr(code_rules_enforcer_module.sys, "stdin", io.StringIO(write_payload))
    exit_code = 0
    try:
        code_rules_enforcer_module.main([])
    except SystemExit as each_exit:
        exit_code = int(each_exit.code or 0)
    captured = capsys.readouterr()
    return captured.out, exit_code


def _run_tdd_with_write_payload(
    file_path: str,
    content: str,
) -> subprocess.CompletedProcess[str]:
    """Drive the TDD enforcer through subprocess with a Write payload.

    Args:
        file_path: The destination path the Write targets.
        content: The production-looking content to write.

    Returns:
        The completed process carrying stdout, stderr, and the exit code.
    """
    write_payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
        }
    )
    return subprocess.run(
        [sys.executable, str(_TDD_SCRIPT)],
        input=write_payload,
        capture_output=True,
        text=True,
        check=False,
    )


def _decision_from(completed: subprocess.CompletedProcess[str]) -> str | None:
    """Extract the permissionDecision from a hook's JSON stdout.

    Args:
        completed: The completed subprocess carrying the hook's stdout.

    Returns:
        The permissionDecision string, or None when stdout is empty.
    """
    if not completed.stdout:
        return None
    parsed = json.loads(completed.stdout)
    hook_output = parsed.get("hookSpecificOutput", {})
    return hook_output.get("permissionDecision")


def test_should_return_true_for_claude_job_dir_tmp_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B1: classifier returns True for a path under $CLAUDE_JOB_DIR/tmp."""
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    scratch_path = str(tmp_path / "tmp" / "scratch.py")
    assert is_ephemeral_script_path(scratch_path) is True


def test_should_return_false_for_os_tempfile_gettempdir_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B2: the shared OS temp directory is not an ephemeral source.

    pytest sandbox fixtures live under tempfile.gettempdir(); matching it
    would exempt the suite's own enforcer test targets.
    """
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    monkeypatch.delenv("CLAUDE_JOB_DIR", raising=False)
    system_temp_root = tempfile.gettempdir()
    scratch_path = str(Path(system_temp_root) / "scratch_work.py")
    assert is_ephemeral_script_path(scratch_path) is False


@pytest.mark.parametrize("env_name", ["TMPDIR", "TEMP", "TMP"])
def test_should_return_false_for_tmpdir_temp_tmp_env_roots(
    env_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B3: $TMPDIR / $TEMP / $TMP are not ephemeral sources.

    A path under one of these env roots that is neither $CLAUDE_JOB_DIR/tmp
    nor root-anchored /tmp must classify False.
    """
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    monkeypatch.delenv("CLAUDE_JOB_DIR", raising=False)
    monkeypatch.setenv(env_name, str(tmp_path / "env_root"))
    scratch_path = str(tmp_path / "env_root" / "scratch.py")
    assert is_ephemeral_script_path(scratch_path) is False


def test_should_return_false_for_pytest_tmp_path_when_job_dir_elsewhere(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard: a pytest tmp_path under %TEMP% returns False.

    This is the exact path class that broke the enforcer suite when the OS
    temp directory was an ephemeral source: pytest tmp_path fixtures live
    under tempfile.gettempdir(), so the enforcer's own test targets must not
    classify as ephemeral. CLAUDE_JOB_DIR points elsewhere (its scratch dir
    lives under .claude-ev/jobs, not %TEMP%).
    """
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path / "elsewhere"))
    pytest_sandbox_target = str(tmp_path / "candidate.py")
    assert is_ephemeral_script_path(pytest_sandbox_target) is False


@pytest.mark.parametrize(
    "raw_path",
    [
        "/tmp/scratch.py",
        "/temp/scratch.py",
        "C:/Temp/scratch.py",
        "c:/tmp/scratch.py",
    ],
)
def test_should_return_true_for_root_anchored_tmp_and_temp(
    raw_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B4: classifier returns True for root-anchored /tmp and /temp paths."""
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    assert is_ephemeral_script_path(raw_path) is True


@pytest.mark.parametrize(
    "lookalike_path",
    [
        "/repo/tmp_helper.py",
        "/repo/temp/foo.py",
        "/repo/src/temperature.py",
        "/repo/contemporary/x.py",
    ],
)
def test_should_return_false_for_lookalike_tmp_temp_paths(
    lookalike_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B5: classifier returns False for paths that merely contain tmp/temp substrings."""
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    assert is_ephemeral_script_path(lookalike_path) is False


def test_should_resolve_relative_path_before_classifying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B6: a relative path resolving under $CLAUDE_JOB_DIR/tmp returns True."""
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    (tmp_path / "tmp").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path / "tmp")
    assert is_ephemeral_script_path("scratch.py") is True


def test_should_return_false_when_job_dir_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B7: with CLAUDE_JOB_DIR unset, a non-temp path returns False."""
    monkeypatch.delenv("CLAUDE_JOB_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    assert is_ephemeral_script_path("/repo/src/orders.py") is False


@pytest.mark.parametrize("truthy_value", ["1", "true", "yes", "on"])
def test_should_return_false_when_disable_override_truthy(
    truthy_value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B8: override set to each truthy value returns False even for a temp path."""
    monkeypatch.setenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", truthy_value)
    assert is_ephemeral_script_path("/tmp/scratch.py") is False


def test_should_classify_nonexistent_path_without_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B9: a path that does not exist is classified by string, with no exception."""
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    classification_result = is_ephemeral_script_path("/tmp/does_not_exist.py")
    assert isinstance(classification_result, bool)
    assert classification_result is True


def test_should_return_false_for_empty_path() -> None:
    """B10: an empty string returns False."""
    assert is_ephemeral_script_path("") is False


def test_should_exit_zero_for_ephemeral_pretooluse_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B11: enforcer main exits 0 with no deny payload for an ephemeral file_path."""
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    ephemeral_path = str(tmp_path / "tmp" / "scratch.py")
    captured_stdout, exit_code = _run_main_with_write_payload(
        ephemeral_path,
        _VIOLATING_PRODUCTION_SOURCE,
        monkeypatch,
        capsys,
    )
    assert exit_code == 0
    assert "deny" not in captured_stdout.lower()


def test_should_exit_zero_for_ephemeral_path_with_hooks_substring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B12: an ephemeral path carrying /hooks/ exits 0 (hook-infra route short-circuited)."""
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    ephemeral_hooks_path = str(tmp_path / "tmp" / "hooks" / "scratch.py")
    captured_stdout, exit_code = _run_main_with_write_payload(
        ephemeral_hooks_path,
        _VIOLATING_PRODUCTION_SOURCE,
        monkeypatch,
        capsys,
    )
    assert exit_code == 0
    assert "deny" not in captured_stdout.lower()


def test_should_return_zero_from_precheck_for_ephemeral_target(
    tmp_path: Path,
) -> None:
    """B13: enforcer CLI returns 0 for an ephemeral root-anchored /tmp --as target."""
    candidate_file = tmp_path / "candidate.py"
    candidate_file.write_text(_VIOLATING_PRODUCTION_SOURCE, encoding="utf-8")
    ephemeral_target = "/tmp/target.py"
    completed = _run_enforcer_cli(["--check", str(candidate_file), "--as", ephemeral_target], extra_env={})
    assert completed.returncode == 0


def test_should_run_full_suite_for_non_ephemeral_target(
    tmp_path: Path,
) -> None:
    """B14: a non-ephemeral violating path still produces a deny payload."""
    candidate_file = tmp_path / "candidate.py"
    candidate_file.write_text(_VIOLATING_PRODUCTION_SOURCE, encoding="utf-8")
    non_ephemeral_target = "/repo/src/orders.py"
    completed = _run_enforcer_cli(
        ["--check", str(candidate_file), "--as", non_ephemeral_target],
        extra_env={},
    )
    assert completed.returncode == 1


def test_should_run_full_suite_when_override_truthy(
    tmp_path: Path,
) -> None:
    """B15: with override set, an ephemeral violating path produces a deny."""
    candidate_file = tmp_path / "candidate.py"
    candidate_file.write_text(_VIOLATING_PRODUCTION_SOURCE, encoding="utf-8")
    ephemeral_target = "/tmp/scratch.py"
    completed = _run_enforcer_cli(
        ["--check", str(candidate_file), "--as", ephemeral_target],
        extra_env={"CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT": "1"},
    )
    assert completed.returncode == 1


def test_should_exempt_same_path_set_on_both_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B21: every ephemeral path exits 0 on both enforcer main and TDD enforcer main."""
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    all_ephemeral_paths = [
        str(tmp_path / "tmp" / "scratch.py"),
        "/tmp/scratch.py",
        "/temp/scratch.py",
    ]
    for each_ephemeral_path in all_ephemeral_paths:
        captured_stdout, exit_code = _run_main_with_write_payload(
            each_ephemeral_path,
            _VIOLATING_PRODUCTION_SOURCE,
            monkeypatch,
            capsys,
        )
        assert exit_code == 0, (
            f"enforcer must exit 0 for ephemeral path {each_ephemeral_path!r}, "
            f"got exit_code={exit_code}, stdout={captured_stdout!r}"
        )
        assert "deny" not in captured_stdout.lower(), (
            f"enforcer must not deny ephemeral path {each_ephemeral_path!r}"
        )
        completed = _run_tdd_with_write_payload(each_ephemeral_path, _VIOLATING_PRODUCTION_SOURCE)
        assert _decision_from(completed) != "deny", (
            f"TDD enforcer must not deny ephemeral path {each_ephemeral_path!r}"
        )
