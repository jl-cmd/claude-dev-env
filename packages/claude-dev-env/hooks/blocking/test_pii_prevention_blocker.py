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
    ALL_BASH_HOSTED_HOOK_ENTRIES,
    ALL_BASH_ONLY_TOOL_NAMES,
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
    assert SYNTHETIC_REAL_EMAIL in deny_reason


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


def test_gh_post_body_with_secret_is_denied() -> None:
    command = (
        f'gh pr comment 12 --body "auth material {SYNTHETIC_GITHUB_TOKEN}"'
    )
    deny_reason = evaluate_bash_command(command, working_directory=None)
    assert deny_reason is not None
    assert "secret" in deny_reason


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
    assert matching_bash_entries[0].applicable_tool_names == ALL_BASH_ONLY_TOOL_NAMES
