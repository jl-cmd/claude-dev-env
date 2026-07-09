"""Behavior tests for the PII prevention PreToolUse hook."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK_DIR = Path(__file__).parent
_HOOKS_DIR = _HOOK_DIR.parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (  # noqa: E402
    ALL_BASH_AND_POWERSHELL_TOOL_NAMES,
    ALL_BASH_HOSTED_HOOK_ENTRIES,
)
from hooks_constants.pre_tool_use_dispatcher_constants import (  # noqa: E402
    ALL_HOSTED_HOOK_ENTRIES,
    ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
)
import pii_prevention_blocker as blocker_module  # noqa: E402
from pii_prevention_blocker import (  # noqa: E402
    evaluate,
    evaluate_bash_command,
    evaluate_staged_commit,
    evaluate_write_edit_payload,
    is_git_commit_shell_command,
)

HOOK_PATH = _HOOK_DIR / "pii_prevention_blocker.py"

SYNTHETIC_GITHUB_TOKEN = "ghp_" + ("C" * 36)
SYNTHETIC_REAL_EMAIL = "owner.fixture@acme-corp.example.io"
SYNTHETIC_HOME_PATH = r"C:\Users\fixture_commit_user\secret.txt"
SYNTHETIC_PRIVATE_IP = "10.44.12.9"
SYNTHETIC_SAFE_BODY = "All checks pass. Contact user@example.com for docs."


def _run_hook(payload: dict[str, object]) -> tuple[int, str]:
    completed = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return completed.returncode, completed.stdout


def test_write_with_real_email_is_denied() -> None:
    deny_reason = evaluate_write_edit_payload(
        "Write",
        {
            "file_path": "docs/notes.md",
            "content": f"Reach me at {SYNTHETIC_REAL_EMAIL}",
        },
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert SYNTHETIC_REAL_EMAIL not in deny_reason


def test_write_with_example_email_is_allowed() -> None:
    deny_reason = evaluate_write_edit_payload(
        "Write",
        {
            "file_path": "docs/notes.md",
            "content": "Reach me at user@example.com",
        },
    )
    assert deny_reason is None


def test_edit_introducing_home_path_is_denied() -> None:
    deny_reason = evaluate_write_edit_payload(
        "Edit",
        {
            "file_path": "README.md",
            "old_string": "path here",
            "new_string": f"path is {SYNTHETIC_HOME_PATH}",
        },
    )
    assert deny_reason is not None
    assert "home-path" in deny_reason


def test_write_to_test_file_is_exempt() -> None:
    deny_reason = evaluate_write_edit_payload(
        "Write",
        {
            "file_path": "packages/hooks/blocking/test_fixture_helper.py",
            "content": f"EMAIL = '{SYNTHETIC_REAL_EMAIL}'",
        },
    )
    assert deny_reason is None


def test_write_to_test_prefixed_markdown_is_not_exempt() -> None:
    deny_reason = evaluate_write_edit_payload(
        "Write",
        {
            "file_path": "test_notes.md",
            "content": f"Reach me at {SYNTHETIC_REAL_EMAIL}",
        },
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_write_with_empty_path_still_scans_content() -> None:
    deny_reason = evaluate_write_edit_payload(
        "Write",
        {
            "file_path": "",
            "content": f"Reach me at {SYNTHETIC_REAL_EMAIL}",
        },
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_write_to_basename_only_self_module_name_is_not_exempt() -> None:
    deny_reason = evaluate_write_edit_payload(
        "Write",
        {
            "file_path": "vendor/pii_scanner.py",
            "content": f"Reach me at {SYNTHETIC_REAL_EMAIL}",
        },
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_write_to_license_prefix_filename_is_not_exempt() -> None:
    deny_reason = evaluate_write_edit_payload(
        "Write",
        {
            "file_path": "LICENSE_leak.env",
            "content": f"Reach me at {SYNTHETIC_REAL_EMAIL}",
        },
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_gh_body_file_fails_closed_when_unreadable(tmp_path: Path) -> None:
    missing_body_file = tmp_path / "missing_pr_body.md"
    command = f'gh pr comment 12 --body-file "{missing_body_file}"'
    deny_reason = evaluate_bash_command(command, working_directory=str(tmp_path))
    assert deny_reason is not None
    assert "body-file" in deny_reason


def test_gh_body_file_reads_relative_path_from_working_directory(
    tmp_path: Path,
) -> None:
    body_file = tmp_path / "pr.md"
    body_file.write_text(f"Reach me at {SYNTHETIC_REAL_EMAIL}\n", encoding="utf-8")
    deny_reason = evaluate_bash_command(
        "gh pr comment 12 --body-file pr.md",
        working_directory=str(tmp_path),
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_gh_post_body_with_secret_is_denied() -> None:
    command = (
        f'gh pr comment 12 --body "auth material {SYNTHETIC_GITHUB_TOKEN}"'
    )
    deny_reason = evaluate_bash_command(command, working_directory=None)
    assert deny_reason is not None
    assert "secret" in deny_reason
    assert SYNTHETIC_GITHUB_TOKEN not in deny_reason


def test_gh_post_clean_body_is_allowed() -> None:
    command = f'gh pr comment 12 --body "{SYNTHETIC_SAFE_BODY}"'
    assert evaluate_bash_command(command, working_directory=None) is None


def test_mcp_github_body_with_private_ip_is_denied() -> None:
    deny_reason = evaluate(
        {
            "tool_name": "mcp__plugin_github_github__add_issue_comment",
            "tool_input": {
                "body": f"Service is at {SYNTHETIC_PRIVATE_IP}",
            },
        }
    )
    assert deny_reason is not None
    assert "private-ip" in deny_reason


def test_subprocess_hook_denies_write_with_token() -> None:
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "src/config.env.example.md",
            "content": f"TOKEN={SYNTHETIC_GITHUB_TOKEN}\n",
        },
    }
    exit_code, stdout_text = _run_hook(payload)
    assert exit_code == 0
    assert stdout_text.strip()
    payload_out = json.loads(stdout_text)
    decision = payload_out["hookSpecificOutput"]["permissionDecision"]
    reason = payload_out["hookSpecificOutput"]["permissionDecisionReason"]
    assert decision == "deny"
    assert "secret" in reason
    assert SYNTHETIC_GITHUB_TOKEN not in reason


def test_subprocess_hook_allows_clean_write() -> None:
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "docs/guide.md",
            "content": "Use user@example.com and C:/Users/<you>/ for samples.\n",
        },
    }
    exit_code, stdout_text = _run_hook(payload)
    assert exit_code == 0
    assert stdout_text.strip() == ""


def test_staged_commit_with_pii_is_denied(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "dev@example.com"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Fixture Dev"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked_file = repository_root / "notes.md"
    tracked_file.write_text(
        f"owner email {SYNTHETIC_REAL_EMAIL}\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", "notes.md"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    deny_reason = evaluate_bash_command(
        "git commit -m test",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert "staged commit" in deny_reason


def test_staged_commit_with_clean_content_is_allowed(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "dev@example.com"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Fixture Dev"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked_file = repository_root / "notes.md"
    tracked_file.write_text(
        "Use user@example.com in docs only.\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", "notes.md"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    deny_reason = evaluate_bash_command(
        "git commit -m test",
        working_directory=str(repository_root),
    )
    assert deny_reason is None


def test_staged_commit_fails_closed_when_git_list_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        blocker_module,
        "list_staged_file_paths",
        lambda _repository_root: (None, "BLOCKED list failure"),
    )
    deny_reason = evaluate_staged_commit(tmp_path)
    assert deny_reason == "BLOCKED list failure"


def test_staged_commit_fails_closed_when_blob_unscannable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        blocker_module,
        "list_staged_file_paths",
        lambda _repository_root: (["binary.bin"], None),
    )
    monkeypatch.setattr(
        blocker_module,
        "read_staged_file_text",
        lambda _repository_root, relative_path: (
            None,
            f"BLOCKED unscannable {relative_path}",
        ),
    )
    deny_reason = evaluate_staged_commit(tmp_path)
    assert deny_reason is not None
    assert "unscannable" in deny_reason
    assert "binary.bin" in deny_reason


def test_dispatcher_roster_hosts_pii_blocker() -> None:
    matching_write_entries = [
        each_entry
        for each_entry in ALL_HOSTED_HOOK_ENTRIES
        if each_entry.script_relative_path == "blocking/pii_prevention_blocker.py"
    ]
    assert len(matching_write_entries) == 1
    assert matching_write_entries[0].applicable_tool_names == ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES
    assert matching_write_entries[0].is_blocking is True
    matching_bash_entries = [
        each_entry
        for each_entry in ALL_BASH_HOSTED_HOOK_ENTRIES
        if each_entry.script_relative_path == "blocking/pii_prevention_blocker.py"
    ]
    assert len(matching_bash_entries) == 1
    assert (
        matching_bash_entries[0].applicable_tool_names
        == ALL_BASH_AND_POWERSHELL_TOOL_NAMES
    )


def test_is_git_commit_shell_command_covers_windows_and_flag_forms() -> None:
    assert is_git_commit_shell_command("git commit -m test")
    assert is_git_commit_shell_command("git.exe commit -m test")
    assert is_git_commit_shell_command("git --no-verify commit -m test")
    assert is_git_commit_shell_command("git -c commit.gpgsign=false commit -m x")
    assert is_git_commit_shell_command('git -C "C:/repo" commit -m x')
    assert is_git_commit_shell_command(r'& "C:\Program Files\Git\cmd\git.exe" commit -m x')
    assert not is_git_commit_shell_command("git status")
    assert not is_git_commit_shell_command("git log --grep commit")
    assert not is_git_commit_shell_command('echo "please git commit"')
    assert not is_git_commit_shell_command("gh pr comment 1 --body 'git commit'")


def _init_repo_with_staged_email(repository_root: Path) -> None:
    repository_root.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "dev@example.com"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Fixture Dev"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked_file = repository_root / "notes.md"
    tracked_file.write_text(
        f"owner email {SYNTHETIC_REAL_EMAIL}\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", "notes.md"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_git_exe_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        "git.exe commit -m test",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert SYNTHETIC_REAL_EMAIL not in deny_reason


def test_git_config_flag_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        "git -c commit.gpgsign=false commit -m test",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_git_no_verify_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        "git --no-verify commit -m test",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_repository_root_unresolved_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(blocker_module, "resolve_repository_root", lambda _cwd: None)
    deny_reason = evaluate_bash_command(
        "git commit -m test",
        working_directory=str(Path.cwd()),
    )
    assert deny_reason is not None
    assert "repository root" in deny_reason


def test_powershell_tool_commit_with_staged_email_is_denied(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate(
        {
            "tool_name": "PowerShell",
            "tool_input": {
                "command": "git commit -m test",
                "working_directory": str(repository_root),
            },
        }
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert SYNTHETIC_REAL_EMAIL not in deny_reason
def test_is_git_commit_shell_command_detects_glued_and_newline_separators() -> None:
    assert is_git_commit_shell_command("git add .;git commit -m x")
    assert is_git_commit_shell_command("cd repo&&git commit -m x")
    assert is_git_commit_shell_command("git add notes.md\ngit commit -m update")
    assert is_git_commit_shell_command("git status\ngit commit -m x")
    assert not is_git_commit_shell_command(
        "gh pr comment 1 --body 'notes\ngit commit -m x'"
    )


def test_newline_separated_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        "git add notes.md\ngit commit -m update",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert "staged commit" in deny_reason


def test_glued_semicolon_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        "git add notes.md;git commit -m update",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_is_git_commit_shell_command_detects_shell_keyword_wrapped_commits() -> None:
    assert is_git_commit_shell_command("if true; then git commit -m x; fi")
    assert is_git_commit_shell_command("for f in a b; do git commit -m x; done")
    assert is_git_commit_shell_command("bash -c 'git commit -m x'")
    assert is_git_commit_shell_command('sh -c "git commit -m x"')


def test_is_git_commit_shell_command_detects_wrapper_prefixed_commits() -> None:
    assert is_git_commit_shell_command("time git commit -m x")
    assert is_git_commit_shell_command("sudo git commit -m x")
    assert is_git_commit_shell_command("env GIT_AUTHOR_NAME=a git commit")
    assert is_git_commit_shell_command("nice git commit -m y")
    assert not is_git_commit_shell_command("sudo cat notes.md")


def test_wrapper_prefixed_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        "env GIT_AUTHOR_NAME=a git commit -m test",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert SYNTHETIC_REAL_EMAIL not in deny_reason


def test_shell_keyword_wrapped_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        "time git commit -m test",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_is_git_commit_shell_command_detects_powershell_command_flag() -> None:
    assert is_git_commit_shell_command('pwsh -NoProfile -Command "git commit -m x"')
    assert is_git_commit_shell_command('powershell -Command "git commit -m x"')
    assert is_git_commit_shell_command("pwsh.exe -Command 'git commit -m x'")
    assert is_git_commit_shell_command('pwsh -c "git commit -m x"')
    assert not is_git_commit_shell_command('pwsh -NoProfile -Command "git status"')


def test_is_git_commit_shell_command_detects_flag_carrying_wrappers() -> None:
    assert is_git_commit_shell_command("nice -n 10 git commit -m x")
    assert is_git_commit_shell_command("stdbuf -oL git commit -m x")
    assert is_git_commit_shell_command("env -i git commit -m x")
    assert is_git_commit_shell_command("env -u NAME git commit -m x")
    assert not is_git_commit_shell_command("nice -n 10 cat notes.md")


def test_is_git_commit_shell_command_detects_combined_interpreter_flags() -> None:
    assert is_git_commit_shell_command('bash -lc "git commit -m x"')
    assert is_git_commit_shell_command("sh -ec 'git commit -m x'")
    assert is_git_commit_shell_command('bash -l -c "git commit -m x"')
    assert not is_git_commit_shell_command('bash -lc "git status"')


def test_powershell_command_flag_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        'pwsh -NoProfile -Command "git commit -m test"',
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert SYNTHETIC_REAL_EMAIL not in deny_reason


def test_flag_carrying_wrapper_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        "nice -n 10 git commit -m test",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert SYNTHETIC_REAL_EMAIL not in deny_reason


def test_combined_interpreter_flag_commit_scans_staged_pii(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_staged_email(repository_root)
    deny_reason = evaluate_bash_command(
        'bash -lc "git commit -m test"',
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert SYNTHETIC_REAL_EMAIL not in deny_reason
