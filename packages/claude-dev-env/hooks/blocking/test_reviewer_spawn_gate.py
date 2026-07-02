"""Unit tests for reviewer_spawn_gate PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import sys
from contextlib import redirect_stderr, redirect_stdout

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "reviewer_spawn_gate",
    _HOOK_DIR / "reviewer_spawn_gate.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

_matches_copilot_trigger = hook_module._matches_copilot_trigger
_matches_bugbot_trigger = hook_module._matches_bugbot_trigger
_reviewer_trigger = hook_module._reviewer_trigger

_SENTINEL_MARKER = hook_module.GATE_SENTINEL_MARKER
_AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME = hook_module.AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME

_COPILOT_TRIGGER_COMMAND = (
    f"{_SENTINEL_MARKER} gh api repos/o/r/pulls/1/requested_reviewers "
    f'-f "reviewers[]=copilot-pull-request-reviewer[bot]"'
)
_BUGBOT_TRIGGER_COMMAND = f'{_SENTINEL_MARKER} python post_fix_reply.py --body "bugbot run"'


def _write_fake_availability_script(tmp_path: pathlib.Path, exit_code: int) -> pathlib.Path:
    fake_script_path = tmp_path / "fake_reviewer_availability.py"
    fake_script_path.write_text(f"import sys\nsys.exit({exit_code})\n", encoding="utf-8")
    return fake_script_path


def _run_hook_with_stdin_text(stdin_text: str) -> tuple[str, str, int]:
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    exit_code = 0
    sys.stdin = io.StringIO(stdin_text)
    try:
        with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
            try:
                hook_module.main()
            except SystemExit as exit_signal:
                exit_code = exit_signal.code if isinstance(exit_signal.code, int) else 0
    finally:
        sys.stdin = sys.__stdin__
    return captured_stdout.getvalue(), captured_stderr.getvalue(), exit_code


def _run_hook(hook_input: dict) -> tuple[str, int]:
    stdout_text, _stderr_text, exit_code = _run_hook_with_stdin_text(json.dumps(hook_input))
    return stdout_text, exit_code


def test_matches_copilot_trigger_true_for_request_reviewers_command() -> None:
    assert _matches_copilot_trigger(_COPILOT_TRIGGER_COMMAND)


def test_matches_copilot_trigger_false_for_unrelated_command() -> None:
    assert not _matches_copilot_trigger("gh pr list")


def test_matches_bugbot_trigger_true_for_rerun_comment_command() -> None:
    assert _matches_bugbot_trigger(_BUGBOT_TRIGGER_COMMAND)


def test_matches_bugbot_trigger_false_for_unrelated_command() -> None:
    assert not _matches_bugbot_trigger("python post_fix_reply.py --body 'looks good'")


def test_reviewer_trigger_returns_none_for_unrecognized_command() -> None:
    assert _reviewer_trigger("gh pr list") is None


def test_main_allows_copilot_shaped_command_with_no_sentinel_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_script_path = _write_fake_availability_script(tmp_path, exit_code=1)
    monkeypatch.setenv(_AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME, str(fake_script_path))
    stdout_text, exit_code = _run_hook(
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "gh api repos/o/r/pulls/1/requested_reviewers "
                    '-f "reviewers[]=copilot-pull-request-reviewer[bot]"'
                )
            },
        }
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_copilot_trigger_when_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_script_path = _write_fake_availability_script(tmp_path, exit_code=0)
    monkeypatch.setenv(_AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME, str(fake_script_path))
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": _COPILOT_TRIGGER_COMMAND}}
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_denies_copilot_trigger_when_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_script_path = _write_fake_availability_script(tmp_path, exit_code=1)
    monkeypatch.setenv(_AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME, str(fake_script_path))
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": _COPILOT_TRIGGER_COMMAND}}
    )
    assert exit_code == 0
    response_payload = json.loads(stdout_text)
    decision_block = response_payload["hookSpecificOutput"]
    assert decision_block["permissionDecision"] == "deny"
    assert "GitHub Copilot" in decision_block["permissionDecisionReason"]


def test_main_denies_copilot_trigger_on_any_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_script_path = _write_fake_availability_script(tmp_path, exit_code=2)
    monkeypatch.setenv(_AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME, str(fake_script_path))
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": _COPILOT_TRIGGER_COMMAND}}
    )
    assert exit_code == 0
    response_payload = json.loads(stdout_text)
    decision_block = response_payload["hookSpecificOutput"]
    assert decision_block["permissionDecision"] == "deny"


def test_main_allows_bugbot_trigger_when_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_script_path = _write_fake_availability_script(tmp_path, exit_code=0)
    monkeypatch.setenv(_AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME, str(fake_script_path))
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": _BUGBOT_TRIGGER_COMMAND}}
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_denies_bugbot_trigger_when_opted_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_script_path = _write_fake_availability_script(tmp_path, exit_code=1)
    monkeypatch.setenv(_AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME, str(fake_script_path))
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": _BUGBOT_TRIGGER_COMMAND}}
    )
    assert exit_code == 0
    response_payload = json.loads(stdout_text)
    decision_block = response_payload["hookSpecificOutput"]
    assert decision_block["permissionDecision"] == "deny"
    assert "Cursor Bugbot" in decision_block["permissionDecisionReason"]


def test_main_allows_marker_command_with_no_recognized_trigger(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_script_path = _write_fake_availability_script(tmp_path, exit_code=1)
    monkeypatch.setenv(_AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME, str(fake_script_path))
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": f"{_SENTINEL_MARKER} gh pr list"}}
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_when_availability_script_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    missing_script_path = tmp_path / "does_not_exist.py"
    monkeypatch.setenv(_AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME, str(missing_script_path))
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": _COPILOT_TRIGGER_COMMAND}}
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_allows_non_bash_tool() -> None:
    stdout_text, exit_code = _run_hook(
        {"tool_name": "Write", "tool_input": {"content": _COPILOT_TRIGGER_COMMAND}}
    )
    assert exit_code == 0
    assert stdout_text == ""


def test_main_with_empty_stdin_exits_silently() -> None:
    stdout_text, stderr_text, exit_code = _run_hook_with_stdin_text("")
    assert exit_code == 0
    assert stdout_text == ""
    assert stderr_text == ""


def test_main_with_invalid_json_stdin_exits_silently() -> None:
    stdout_text, stderr_text, exit_code = _run_hook_with_stdin_text("{broken")
    assert exit_code == 0
    assert stdout_text == ""
    assert stderr_text == ""
