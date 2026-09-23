"""Behavior tests for the nested project hooks forwarder.

Each case builds a session directory that holds child checkouts, runs the hook
script the way Claude Code does (payload on stdin, ``CLAUDE_PROJECT_DIR`` set
to the session directory), and reads the exit code and output it produces.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

HOOK_SCRIPT_PATH = pathlib.Path(__file__).parent / "nested_project_hooks.py"
BLOCKING_EXIT_CODE = 2


def _make_checkout(
    session_directory: pathlib.Path,
    checkout_name: str,
    all_hook_groups_by_event: dict[str, list[dict[str, object]]],
) -> pathlib.Path:
    checkout_directory = session_directory / checkout_name
    (checkout_directory / ".git").mkdir(parents=True)
    settings_directory = checkout_directory / ".claude"
    settings_directory.mkdir()
    (settings_directory / "settings.json").write_text(
        json.dumps({"hooks": all_hook_groups_by_event}), encoding="utf-8"
    )
    return checkout_directory


def _command_group(matcher: str, command: str) -> dict[str, object]:
    return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}


def _run_hook(
    session_directory: pathlib.Path, payload: dict[str, object]
) -> subprocess.CompletedProcess[str]:
    hook_environment = dict(os.environ)
    hook_environment["CLAUDE_PROJECT_DIR"] = str(session_directory)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=hook_environment,
        check=False,
        timeout=60,
    )


def _pre_tool_use_payload(tool_name: str) -> dict[str, object]:
    return {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": {}}


def _session_start_payload() -> dict[str, object]:
    return {"hook_event_name": "SessionStart", "source": "startup"}


def test_should_run_a_child_session_start_hook_inside_that_child(
    tmp_path: pathlib.Path,
) -> None:
    record_path = tmp_path / "record.txt"
    checkout_directory = _make_checkout(
        tmp_path / "session",
        "alpha",
        {
            "SessionStart": [
                _command_group(
                    "",
                    f'echo "$CLAUDE_PROJECT_DIR|$(pwd)" > "{record_path}"',
                )
            ]
        },
    )

    completed_process = _run_hook(tmp_path / "session", _session_start_payload())

    assert completed_process.returncode == 0
    resolved_checkout = str(checkout_directory.resolve())
    project_directory, working_directory = (
        record_path.read_text(encoding="utf-8").strip().split("|")
    )
    assert str(pathlib.Path(project_directory).resolve()) == resolved_checkout
    assert str(pathlib.Path(working_directory).resolve()) == resolved_checkout


def test_should_carry_child_session_start_output_as_additional_context(
    tmp_path: pathlib.Path,
) -> None:
    _make_checkout(
        tmp_path,
        "alpha",
        {"SessionStart": [_command_group("", "echo alpha is ready")]},
    )
    _make_checkout(
        tmp_path,
        "beta",
        {"SessionStart": [_command_group("", "echo beta is ready")]},
    )

    completed_process = _run_hook(tmp_path, _session_start_payload())

    assert completed_process.returncode == 0
    hook_output = json.loads(completed_process.stdout)
    additional_context = hook_output["hookSpecificOutput"]["additionalContext"]
    assert hook_output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "alpha is ready" in additional_context
    assert "beta is ready" in additional_context
    assert additional_context.index("alpha") < additional_context.index("beta")


def test_should_block_a_tool_call_when_a_child_hook_exits_two(
    tmp_path: pathlib.Path,
) -> None:
    _make_checkout(
        tmp_path,
        "alpha",
        {"PreToolUse": [_command_group("Bash", "echo the gate refused this >&2; exit 2")]},
    )

    completed_process = _run_hook(tmp_path, _pre_tool_use_payload("Bash"))

    assert completed_process.returncode == BLOCKING_EXIT_CODE
    assert "the gate refused this" in completed_process.stderr


def test_should_pass_a_child_deny_decision_through(tmp_path: pathlib.Path) -> None:
    deny_output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "no receipt for this commit",
        }
    }
    _make_checkout(
        tmp_path,
        "alpha",
        {
            "PreToolUse": [
                _command_group(
                    "Bash|mcp__github__merge_pull_request",
                    f"echo '{json.dumps(deny_output)}'",
                )
            ]
        },
    )

    completed_process = _run_hook(
        tmp_path, _pre_tool_use_payload("mcp__github__merge_pull_request")
    )

    assert completed_process.returncode == 0
    assert json.loads(completed_process.stdout) == deny_output


def test_should_not_forward_a_child_allow_decision(tmp_path: pathlib.Path) -> None:
    allow_output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    _make_checkout(
        tmp_path,
        "alpha",
        {"PreToolUse": [_command_group("", f"echo '{json.dumps(allow_output)}'")]},
    )

    completed_process = _run_hook(tmp_path, _pre_tool_use_payload("Bash"))

    assert completed_process.returncode == 0
    assert completed_process.stdout.strip() == ""


def test_should_skip_a_child_hook_whose_matcher_names_another_tool(
    tmp_path: pathlib.Path,
) -> None:
    _make_checkout(
        tmp_path,
        "alpha",
        {"PreToolUse": [_command_group("Write|Edit", "exit 2")]},
    )

    completed_process = _run_hook(tmp_path, _pre_tool_use_payload("Bash"))

    assert completed_process.returncode == 0


def test_should_do_nothing_when_the_session_directory_is_a_checkout(
    tmp_path: pathlib.Path,
) -> None:
    (tmp_path / ".git").mkdir()
    _make_checkout(
        tmp_path,
        "alpha",
        {"PreToolUse": [_command_group("", "exit 2")]},
    )

    completed_process = _run_hook(tmp_path, _pre_tool_use_payload("Bash"))

    assert completed_process.returncode == 0
    assert completed_process.stdout.strip() == ""


def test_should_skip_a_child_directory_that_is_not_a_checkout(
    tmp_path: pathlib.Path,
) -> None:
    checkout_directory = _make_checkout(
        tmp_path,
        "alpha",
        {"PreToolUse": [_command_group("", "exit 2")]},
    )
    (checkout_directory / ".git").rmdir()

    completed_process = _run_hook(tmp_path, _pre_tool_use_payload("Bash"))

    assert completed_process.returncode == 0


def test_should_let_the_call_through_when_a_child_hook_fails_to_start(
    tmp_path: pathlib.Path,
) -> None:
    _make_checkout(
        tmp_path,
        "alpha",
        {"PreToolUse": [_command_group("", "a-command-that-does-not-exist")]},
    )

    completed_process = _run_hook(tmp_path, _pre_tool_use_payload("Bash"))

    assert completed_process.returncode == 0


@pytest.mark.parametrize("unreadable_settings", ["{not json", "[]", '{"hooks": []}'])
def test_should_skip_a_child_whose_settings_cannot_be_read(
    tmp_path: pathlib.Path, unreadable_settings: str
) -> None:
    checkout_directory = _make_checkout(tmp_path, "alpha", {})
    (checkout_directory / ".claude" / "settings.json").write_text(
        unreadable_settings, encoding="utf-8"
    )

    completed_process = _run_hook(tmp_path, _pre_tool_use_payload("Bash"))

    assert completed_process.returncode == 0
