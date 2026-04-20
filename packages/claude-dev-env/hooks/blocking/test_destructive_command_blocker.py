"""Tests for destructive-command-blocker hook."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).parent / "destructive_command_blocker.py"
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


def _run_hook_with_fake_home(
    payload: dict,
    fake_home: Path,
    working_directory: Path,
    disable_ephemeral_auto_allow: bool = True,
) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    child_environment.pop(GH_REDIRECT_ACTIVE_ENV_VAR, None)
    child_environment["HOME"] = str(fake_home)
    child_environment["USERPROFILE"] = str(fake_home)
    if disable_ephemeral_auto_allow:
        child_environment["CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW"] = "1"
    else:
        child_environment.pop("CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
        cwd=str(working_directory),
    )


def _write_settings_with_allow_list(fake_home: Path, allow_list: list[str]) -> None:
    claude_directory = fake_home / ".claude"
    claude_directory.mkdir(parents=True, exist_ok=True)
    settings_payload = {"hooks": {"allowGitResetHardProjects": allow_list}}
    (claude_directory / "settings.json").write_text(
        json.dumps(settings_payload), encoding="utf-8"
    )


def test_git_reset_hard_allowed_when_cwd_matches_settings_allow_list(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    project_directory = tmp_path / "approved_project"
    project_directory.mkdir()
    project_path_forward = str(project_directory).replace("\\", "/")
    _write_settings_with_allow_list(fake_home, [project_path_forward])
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, project_directory)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_git_reset_hard_asks_when_cwd_not_in_settings_allow_list(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    approved_directory = tmp_path / "approved_project"
    approved_directory.mkdir()
    unapproved_directory = tmp_path / "unapproved_project"
    unapproved_directory.mkdir()
    approved_path_forward = str(approved_directory).replace("\\", "/")
    _write_settings_with_allow_list(fake_home, [approved_path_forward])
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, unapproved_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "git reset --hard" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_git_reset_hard_asks_when_settings_missing(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    project_directory = tmp_path / "unapproved_project"
    project_directory.mkdir()
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, project_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_git_reset_hard_asks_when_allow_list_is_empty(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    project_directory = tmp_path / "some_project"
    project_directory.mkdir()
    _write_settings_with_allow_list(fake_home, [])
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, project_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_git_reset_hard_allowed_in_linked_git_worktree(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    main_repository = tmp_path / "main_repository"
    main_repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=main_repository, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=main_repository, check=True)
    worktree_directory = tmp_path / "worktree_copy"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "feature", str(worktree_directory)],
        cwd=main_repository,
        check=True,
    )
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, worktree_directory, disable_ephemeral_auto_allow=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_git_reset_hard_allowed_when_path_contains_worktrees_segment(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    worktree_directory = tmp_path / "worktrees" / "some_feature"
    worktree_directory.mkdir(parents=True)
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, worktree_directory, disable_ephemeral_auto_allow=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_git_reset_hard_allowed_under_os_temp_directory() -> None:
    fake_home = Path(tempfile.mkdtemp(prefix="home_"))
    working_directory = Path(tempfile.mkdtemp(prefix="ephemeral_work_"))
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, working_directory, disable_ephemeral_auto_allow=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_git_reset_hard_asks_in_plain_directory_with_no_settings(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    plain_directory = tmp_path / "regular_project"
    plain_directory.mkdir()
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, plain_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_git_reset_hard_asks_when_settings_file_is_invalid_json(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    (fake_home / ".claude").mkdir(parents=True)
    (fake_home / ".claude" / "settings.json").write_text(
        "{not valid json", encoding="utf-8"
    )
    project_directory = tmp_path / "unapproved_project"
    project_directory.mkdir()
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, project_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
