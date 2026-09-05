"""Behavior tests for the Bash PostToolUse dispatcher.

One interpreter start runs every hosted PostToolUse hook a Bash call fires.
The unit tests pin selection and call order with a fake
runner; the end-to-end test drives the real hosted hooks through a real
payload and confirms the recorder's own real side effect lands.
``hooks/conftest.py`` already puts the hooks and blocking directories on
sys.path for test collection, so this file needs no bootstrap of its own.
"""

import io
import json
import sys
from pathlib import Path

import pytest

from bash_post_call_dispatcher import (
    additional_context_from_hook_output,
    dispatch,
    main,
    select_applicable_entries,
)
from hooks_constants.bash_pre_tool_use_dispatcher_constants import BASH_TOOL_NAME
from hooks_constants.hosted_hook_runner import HostedHookRun
from tdd_enforcer_parts import content_hash_store

_ALL_EXPECTED_ROSTER_PATHS = [
    "observability/test_failure_recorder.py",
    "advisory/pr_done_reminder.py",
]


def test_select_applicable_entries_returns_the_hosted_hooks_for_bash() -> None:
    all_entries = select_applicable_entries(BASH_TOOL_NAME)
    all_script_paths = [each_entry.script_relative_path for each_entry in all_entries]
    assert all_script_paths == _ALL_EXPECTED_ROSTER_PATHS


def test_select_applicable_entries_returns_none_for_a_write_tool() -> None:
    assert select_applicable_entries("Write") == []


def test_dispatch_runs_every_hosted_hook_in_roster_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_call_paths: list[str] = []

    def _fake_run_hook(script_path: str, payload_text: str) -> HostedHookRun:
        del payload_text
        all_call_paths.append(Path(script_path).name)
        return HostedHookRun(captured_stdout="", did_crash=False)

    monkeypatch.setattr("bash_post_call_dispatcher.run_hook_capturing_output", _fake_run_hook)

    dispatch('{"tool_name": "Bash"}', BASH_TOOL_NAME)

    assert all_call_paths == [Path(each_path).name for each_path in _ALL_EXPECTED_ROSTER_PATHS]


def test_dispatch_forwards_hosted_hook_additional_context_as_one_payload(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    context_by_hook = {
        "test_failure_recorder.py": "",
        "pr_done_reminder.py": json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "PR #42"}}
        ),
    }

    def _fake_run_hook(script_path: str, payload_text: str) -> HostedHookRun:
        del payload_text
        return HostedHookRun(
            captured_stdout=context_by_hook[Path(script_path).name], did_crash=False
        )

    monkeypatch.setattr("bash_post_call_dispatcher.run_hook_capturing_output", _fake_run_hook)

    dispatch('{"tool_name": "Bash"}', BASH_TOOL_NAME)

    emitted = json.loads(capsys.readouterr().out)
    assert emitted == {
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "PR #42"}
    }
    assert "decision" not in emitted


def test_dispatch_writes_nothing_when_no_hosted_hook_printed_context(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _fake_run_hook(script_path: str, payload_text: str) -> HostedHookRun:
        del script_path, payload_text
        return HostedHookRun(captured_stdout="", did_crash=False)

    monkeypatch.setattr("bash_post_call_dispatcher.run_hook_capturing_output", _fake_run_hook)

    dispatch('{"tool_name": "Bash"}', BASH_TOOL_NAME)

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "captured_stdout",
    ["", "   ", "not json", "[]", '{"decision": "block"}', '{"hookSpecificOutput": {}}'],
)
def test_additional_context_from_hook_output_ignores_non_context_output(
    captured_stdout: str,
) -> None:
    assert additional_context_from_hook_output(captured_stdout) is None


def test_main_exits_zero_and_writes_nothing_to_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = json.dumps({"tool_name": "Write", "tool_input": {}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

    with pytest.raises(SystemExit) as raised_exit:
        main()

    assert int(raised_exit.value.code or 0) == 0
    assert capsys.readouterr().out == ""


def test_end_to_end_real_hosted_hooks_record_a_real_pytest_failure(tmp_path: Path) -> None:
    """Drive the real recorder through the dispatcher."""
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_fulfill(): assert False\n")
    session_id = "post-dispatcher-session"
    failing_output = (
        "Error: Exit code 1\n"
        "FAILED test_orders.py::test_fulfill - AssertionError\n"
        "1 failed in 0.02s"
    )
    payload = json.dumps(
        {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "tool_name": "Bash",
            "tool_input": {"command": "pytest test_orders.py"},
            "tool_response": failing_output,
        }
    )

    dispatch(payload, BASH_TOOL_NAME)

    state_file = content_hash_store._state_file_path(session_id, str(tmp_path))
    state = json.loads(state_file.read_text())
    entry = state[content_hash_store._state_key_for(test_file)]
    assert entry[content_hash_store.STORED_FAILURE_EXIT_STATUS_KEY] == 1
