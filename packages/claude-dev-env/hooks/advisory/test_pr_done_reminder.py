"""Behavior tests for the PR done-checklist context reminder.

The hook is a PostToolUse observer on Bash. It never blocks. These tests pin
three things: which commands wake it, what the checklist says for each live
PR state, and that a probe failure stays quiet. The ``gh`` probe is faked at
the subprocess boundary so no test touches the network.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

try:
    advisory_directory = str(Path(__file__).resolve().parent)
    if advisory_directory not in sys.path:
        sys.path.insert(0, advisory_directory)
    import pr_done_reminder
except ImportError as import_error:
    raise ImportError(
        "test_pr_done_reminder: cannot import its sibling modules; "
        "ensure the advisory directory is importable."
    ) from import_error


_CLEAN_PR_OBJECT: dict[str, object] = {
    "number": 42,
    "url": "https://github.com/acme/widgets/pull/42",
    "isDraft": True,
    "mergeable": "MERGEABLE",
    "mergeStateStatus": "CLEAN",
    "statusCheckRollup": [
        {"name": "pytest", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"context": "lint", "state": "SUCCESS"},
    ],
    "labels": [],
}


def _payload(command: str, tool_response: object = None) -> str:
    response: object = {"stdout": "", "stderr": ""} if tool_response is None else tool_response
    return json.dumps(
        {
            "session_id": "reminder-session",
            "cwd": "C:/repo",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": response,
        }
    )


def _fake_gh(pr_object: dict[str, object] | None, stderr: str = "") -> object:
    def _run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        if pr_object is None:
            return subprocess.CompletedProcess([], 1, stdout="", stderr=stderr)
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(pr_object), stderr="")

    return _run


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload_text: str,
    fake_gh: object,
) -> str:
    monkeypatch.setattr(pr_done_reminder.subprocess, "run", fake_gh)
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
    pr_done_reminder.main()
    return capsys.readouterr().out


def _additional_context(stdout_text: str) -> str:
    return str(json.loads(stdout_text)["hookSpecificOutput"]["additionalContext"])


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push -u origin feat/x",
        "git -C C:/repo push origin HEAD",
        "gh pr create --draft --title t --body-file b.md",
        "git add -A && git commit -F m.txt && git push",
        "git -c push.default=current push",
        "git --git-dir=C:/repo/.git push",
        'pwsh -NoProfile -Command "git push -u origin feat/x"',
        "pwsh -NoProfile -Command 'gh pr create --draft --fill'",
        'powershell -Command "git add -A; git push"',
    ],
)
def test_should_wake_on_git_push_and_gh_pr_create(command: str) -> None:
    assert pr_done_reminder.command_triggers_reminder(command) is True


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git pull",
        "git stash push -u -q -- packages",
        "git log --grep push",
        "git commit -m push",
        "gh pr view 42",
        "gh pr ready --undo",
        "echo git push",
        'pwsh -NoProfile -Command "git status"',
        "pytest tests/",
    ],
)
def test_should_stay_quiet_for_other_commands(command: str) -> None:
    assert pr_done_reminder.command_triggers_reminder(command) is False


def test_should_say_done_when_mergeable_and_checks_pass() -> None:
    context = pr_done_reminder.build_reminder_context(_CLEAN_PR_OBJECT)

    assert context.startswith("=== PR DONE CHECKLIST")
    assert "never a block" in context
    assert "DONE. Add the label now:" in context
    assert "gh pr edit 42 --add-label done" in context
    assert "NOT DONE" not in context


def test_should_say_not_done_and_name_the_conflict_fix() -> None:
    conflicted = {**_CLEAN_PR_OBJECT, "mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"}

    context = pr_done_reminder.build_reminder_context(conflicted)

    assert "NOT DONE" in context
    assert "CONFLICTS with the base branch" in context
    assert "gh pr view 42 --json mergeable" in context
    assert "gh pr edit 42 --add-label" not in context


def test_should_count_failing_and_pending_checks() -> None:
    mixed_checks = {
        **_CLEAN_PR_OBJECT,
        "statusCheckRollup": [
            {"name": "pytest", "status": "COMPLETED", "conclusion": "FAILURE"},
            {"name": "mypy", "status": "IN_PROGRESS", "conclusion": ""},
            {"context": "lint", "state": "PENDING"},
            {"context": "docs", "state": "SUCCESS"},
        ],
    }

    context = pr_done_reminder.build_reminder_context(mixed_checks)

    assert "1 failing" in context
    assert "2 pending" in context
    assert "4 total" in context
    assert "NOT DONE" in context


def test_should_tell_the_agent_to_wait_when_github_is_still_computing() -> None:
    unknown = {**_CLEAN_PR_OBJECT, "mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN"}

    context = pr_done_reminder.build_reminder_context(unknown)

    assert "still computing" in context
    assert "NOT DONE" in context


def test_should_report_the_done_label_when_already_set() -> None:
    labeled = {**_CLEAN_PR_OBJECT, "labels": [{"name": "done"}]}

    context = pr_done_reminder.build_reminder_context(labeled)

    assert "Label done:  set" in context


def test_main_should_emit_additional_context_after_a_successful_push(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stdout_text = _run_main(monkeypatch, capsys, _payload("git push"), _fake_gh(_CLEAN_PR_OBJECT))

    payload = json.loads(stdout_text)
    assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "permissionDecision" not in payload["hookSpecificOutput"]
    assert "decision" not in payload
    assert "PR #42" in _additional_context(stdout_text)


def test_main_should_also_serve_the_powershell_tool(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = json.loads(_payload("git push"))
    payload["tool_name"] = "PowerShell"

    stdout_text = _run_main(monkeypatch, capsys, json.dumps(payload), _fake_gh(_CLEAN_PR_OBJECT))

    assert "PR #42" in _additional_context(stdout_text)


def test_main_should_stay_quiet_when_the_push_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failed_push = _payload("git push", "Error: Exit code 1\nrejected")

    assert _run_main(monkeypatch, capsys, failed_push, _fake_gh(_CLEAN_PR_OBJECT)) == ""


def test_main_should_stay_quiet_for_a_non_trigger_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_main(monkeypatch, capsys, _payload("git status"), _fake_gh(_CLEAN_PR_OBJECT)) == ""


def test_main_should_remind_to_open_a_pr_when_the_branch_has_none(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    no_pr = _fake_gh(None, stderr='no pull requests found for branch "feat/x"')

    context = _additional_context(_run_main(monkeypatch, capsys, _payload("git push"), no_pr))

    assert "No open pull request found" in context
    assert "gh pr create --draft" in context


def test_main_should_stay_quiet_on_any_other_gh_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gh_down = _fake_gh(None, stderr="error connecting to api.github.com")

    assert _run_main(monkeypatch, capsys, _payload("git push"), gh_down) == ""
