"""Tests for issue_tracker_commit_reminder — PreToolUse commit/push reminder.

Each test drives the real ``main()`` with a Bash tool payload on stdin, so the
token-aware git match and the allow-plus-additionalContext output run through the
production code path.
"""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import issue_tracker_commit_reminder as reminder
import pytest
from hooks_constants.issue_tracker_commit_reminder_constants import (
    ADDITIONAL_CONTEXT_KEY,
    ALLOW_PERMISSION_DECISION,
    HOOK_EVENT_NAME_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    ISSUE_TRACKER_COMMIT_REMINDER_TEXT,
    PERMISSION_DECISION_KEY,
    PRE_TOOL_USE_EVENT_NAME,
)


def _run_main_with_command(command_text: str) -> str:
    """Return stdout from running main() with a Bash command payload on stdin."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command_text}}
    captured_stdout = StringIO()
    with (
        patch("sys.stdin", StringIO(json.dumps(payload))),
        patch("sys.stdout", captured_stdout),
        pytest.raises(SystemExit),
    ):
        reminder.main()
    return captured_stdout.getvalue()


@pytest.mark.parametrize(
    "commit_or_push_command",
    [
        "git commit -m 'done'",
        "git push",
        "git -C /repo push origin main",
        "cd repo && git commit --amend",
        "git.exe commit -m x",
    ],
)
def test_commit_or_push_returns_allow_with_reminder(
    commit_or_push_command: str,
) -> None:
    emitted = json.loads(_run_main_with_command(commit_or_push_command))
    nested_output = emitted[HOOK_SPECIFIC_OUTPUT_KEY]
    assert nested_output[HOOK_EVENT_NAME_KEY] == PRE_TOOL_USE_EVENT_NAME
    assert nested_output[PERMISSION_DECISION_KEY] == ALLOW_PERMISSION_DECISION
    assert nested_output[ADDITIONAL_CONTEXT_KEY] == ISSUE_TRACKER_COMMIT_REMINDER_TEXT


@pytest.mark.parametrize(
    "non_commit_command",
    [
        "ls -la",
        "git status",
        "git log --oneline",
        "echo git commit",
        "npm run build",
    ],
)
def test_non_git_commit_stays_silent(non_commit_command: str) -> None:
    output = _run_main_with_command(non_commit_command)
    assert output.strip() == ""


@pytest.mark.parametrize(
    "matching_command",
    ["git commit", "git push", "git -C /repo commit -m y"],
)
def test_is_git_commit_or_push_command_matches(matching_command: str) -> None:
    assert reminder.is_git_commit_or_push_command(matching_command) is True


@pytest.mark.parametrize(
    "non_matching_command",
    ["git status", "ls", "echo push", "git remote -v"],
)
def test_is_git_commit_or_push_command_rejects(non_matching_command: str) -> None:
    assert reminder.is_git_commit_or_push_command(non_matching_command) is False


def test_build_reminder_payload_carries_the_reminder_text() -> None:
    nested_output = reminder.build_reminder_payload()[HOOK_SPECIFIC_OUTPUT_KEY]
    assert nested_output[PERMISSION_DECISION_KEY] == ALLOW_PERMISSION_DECISION
    assert nested_output[ADDITIONAL_CONTEXT_KEY] == ISSUE_TRACKER_COMMIT_REMINDER_TEXT
