"""Tests for destructive-command-blocker hook."""

import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).parent / "destructive-command-blocker.py"
GH_GATE_USER_FACING_PREFIX = "[gh-gate]"
GH_REDIRECT_ACTIVE_ENV_VAR = "CLAUDE_GH_REDIRECT_ACTIVE"
GH_REDIRECT_ACTIVE_VALUE = "1"


def _run_hook(
    payload: dict,
    gh_redirect_active: bool = True,
) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    if gh_redirect_active:
        child_environment[GH_REDIRECT_ACTIVE_ENV_VAR] = GH_REDIRECT_ACTIVE_VALUE
    else:
        child_environment.pop(GH_REDIRECT_ACTIVE_ENV_VAR, None)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
    )


def _make_bash_payload(command: str) -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def test_denies_gh_issue_comment_as_redirect_duplicate_guard() -> None:
    payload = _make_bash_payload(
        'gh issue comment 83 --repo jl-cmd/claude-code-config --body "hello"'
    )
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        "gh issue comment" in response["hookSpecificOutput"]["permissionDecisionReason"]
    )
    assert (
        "duplicate execution"
        in response["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_denies_gh_pr_comment_as_redirect_duplicate_guard() -> None:
    payload = _make_bash_payload('gh pr comment 42 --body "ok"')
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gh pr comment" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_denies_gh_pr_review_as_redirect_duplicate_guard() -> None:
    payload = _make_bash_payload("gh pr review 42 --approve")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gh pr review" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_denies_gh_api_post_comment_as_redirect_duplicate_guard() -> None:
    payload = _make_bash_payload(
        "gh api /repos/owner/name/issues/1/comments -X POST -f body=hello"
    )
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_suppresses_output_on_gh_redirect_deny() -> None:
    payload = _make_bash_payload('gh issue comment 1 --body "x"')
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["suppressOutput"] is True
    assert response["systemMessage"].startswith(GH_GATE_USER_FACING_PREFIX)


def test_asks_on_rm_rf_still_works() -> None:
    payload = _make_bash_payload("rm -rf /tmp/somewhere")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "rm -rf" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_asks_on_git_push_force_still_works() -> None:
    payload = _make_bash_payload("git push --force origin main")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert (
        "git push --force" in response["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_allows_plain_command_without_destructive_pattern() -> None:
    payload = _make_bash_payload("ls -la")
    result = _run_hook(payload)
    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_ignores_non_bash_tool() -> None:
    payload = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}
    result = _run_hook(payload)
    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_gh_issue_comment_is_allowed_when_redirect_env_var_is_unset() -> None:
    payload = _make_bash_payload('gh issue comment 83 --body "hello"')

    result = _run_hook(payload, gh_redirect_active=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_gh_pr_comment_is_allowed_when_redirect_env_var_is_unset() -> None:
    payload = _make_bash_payload('gh pr comment 42 --body "ok"')

    result = _run_hook(payload, gh_redirect_active=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_gh_pr_review_is_allowed_when_redirect_env_var_is_unset() -> None:
    payload = _make_bash_payload("gh pr review 42 --approve")

    result = _run_hook(payload, gh_redirect_active=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_gh_api_post_comment_is_allowed_when_redirect_env_var_is_unset() -> None:
    payload = _make_bash_payload(
        "gh api /repos/owner/name/issues/1/comments -X POST -f body=hello"
    )

    result = _run_hook(payload, gh_redirect_active=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_still_asks_when_redirect_env_var_is_unset() -> None:
    payload = _make_bash_payload("rm -rf /tmp/somewhere")

    result = _run_hook(payload, gh_redirect_active=False)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
