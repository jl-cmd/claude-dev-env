"""Behavior tests for the session_edit_stage_gate PreToolUse hook.

Each test builds a real git repository in a temporary directory, records a
session-edit set in a redirected temp directory, and runs the hook script as a
subprocess with a PreToolUse JSON payload on stdin — the exact production
invocation path. Environment overrides point ``tempfile.gettempdir`` at the
per-test temp directory (so the hook reads the test's session-edit file) and
point the home directory at a per-test directory (so the block log stays out of
the real home).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_HOOK_DIR = Path(__file__).resolve().parent
_HOOKS_TREE = _HOOK_DIR.parent
for each_path in (str(_HOOKS_TREE),):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    ALL_EDITED_FILE_PATHS_KEY,
    SESSION_EDIT_FILE_PREFIX,
    SESSION_EDIT_FILE_SUFFIX,
)

HOOK_PATH = _HOOK_DIR / "session_edit_stage_gate.py"
_SESSION_ID = "gate-session-1"


def _clean_git_environment() -> dict[str, str]:
    return {
        each_key: each_value
        for each_key, each_value in os.environ.items()
        if not each_key.startswith("GIT_")
    }


def run_git(repository_root: Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository_root), *git_arguments],
        check=True,
        capture_output=True,
        env=_clean_git_environment(),
    )


def initialize_repository(repository_root: Path) -> None:
    run_git(repository_root, "init")
    run_git(repository_root, "config", "user.email", "tests@example.com")
    run_git(repository_root, "config", "user.name", "Gate Tests")


def prepare_repository_with_unstaged_edit(repository_root: Path) -> Path:
    initialize_repository(repository_root)
    tracked_file = repository_root / "widget.py"
    tracked_file.write_text("x = 1\n", encoding="utf-8")
    run_git(repository_root, "add", "widget.py")
    run_git(repository_root, "commit", "-m", "add widget")
    tracked_file.write_text("x = 2\n", encoding="utf-8")
    return tracked_file


def write_session_edits(temp_directory: Path, session_id: str, absolute_paths: list[Path]) -> None:
    edit_file = temp_directory / f"{SESSION_EDIT_FILE_PREFIX}{session_id}{SESSION_EDIT_FILE_SUFFIX}"
    payload = {ALL_EDITED_FILE_PATHS_KEY: [str(each_path) for each_path in absolute_paths]}
    edit_file.write_text(json.dumps(payload), encoding="utf-8")


def run_hook(
    command: str,
    session_id: str,
    cwd: Path,
    temp_directory: Path,
    home_directory: Path,
) -> subprocess.CompletedProcess[str]:
    environment = _clean_git_environment()
    environment["TMP"] = str(temp_directory)
    environment["TEMP"] = str(temp_directory)
    environment["TMPDIR"] = str(temp_directory)
    environment["USERPROFILE"] = str(home_directory)
    environment["HOME"] = str(home_directory)
    payload = json.dumps({"session_id": session_id, "tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        check=False,
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=environment,
        timeout=60,
    )


def _make_directories(tmp_path: Path) -> tuple[Path, Path, Path]:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    temp_directory = tmp_path / "tmp"
    temp_directory.mkdir()
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    return repository_root, temp_directory, home_directory


def parse_denial(hook_stdout: str) -> dict:
    return json.loads(hook_stdout)["hookSpecificOutput"]


def test_denies_commit_dropping_session_edited_unstaged_file(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    write_session_edits(temp_directory, _SESSION_ID, [tracked_file.resolve()])
    completed_hook = run_hook(
        "git commit -m update", _SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert completed_hook.returncode == 0
    denial = parse_denial(completed_hook.stdout)
    assert denial["permissionDecision"] == "deny"
    assert "widget.py" in denial["permissionDecisionReason"]


def test_deny_writes_hook_block_log(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    write_session_edits(temp_directory, _SESSION_ID, [tracked_file.resolve()])
    run_hook("git commit -m update", _SESSION_ID, repository_root, temp_directory, home_directory)
    logs_directory = home_directory / ".claude" / "logs"
    all_log_files = list(logs_directory.glob("*.log"))
    assert all_log_files
    all_log_text = "".join(each_file.read_text(encoding="utf-8") for each_file in all_log_files)
    assert "session_edit_stage_gate.py" in all_log_text


def test_allows_commit_when_session_edited_file_is_staged(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    run_git(repository_root, "add", "widget.py")
    write_session_edits(temp_directory, _SESSION_ID, [tracked_file.resolve()])
    completed_hook = run_hook(
        "git commit -m update", _SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_allows_commit_all_flag(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    write_session_edits(temp_directory, _SESSION_ID, [tracked_file.resolve()])
    completed_hook = run_hook(
        "git commit -a -m update", _SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_allows_pathspec_commit(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    write_session_edits(temp_directory, _SESSION_ID, [tracked_file.resolve()])
    completed_hook = run_hook(
        "git commit -m update widget.py",
        _SESSION_ID,
        repository_root,
        temp_directory,
        home_directory,
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_allows_partial_commit_marker(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    write_session_edits(temp_directory, _SESSION_ID, [tracked_file.resolve()])
    completed_hook = run_hook(
        "git commit -m update # partial-commit",
        _SESSION_ID,
        repository_root,
        temp_directory,
        home_directory,
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_allows_amend_still_gates(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    write_session_edits(temp_directory, _SESSION_ID, [tracked_file.resolve()])
    completed_hook = run_hook(
        "git commit --amend -m update",
        _SESSION_ID,
        repository_root,
        temp_directory,
        home_directory,
    )
    assert completed_hook.returncode == 0
    denial = parse_denial(completed_hook.stdout)
    assert denial["permissionDecision"] == "deny"


def test_allows_when_no_tracker_file(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    prepare_repository_with_unstaged_edit(repository_root)
    completed_hook = run_hook(
        "git commit -m update", _SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_allows_non_commit_command(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    write_session_edits(temp_directory, _SESSION_ID, [tracked_file.resolve()])
    completed_hook = run_hook(
        "git status", _SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_allows_when_unstaged_file_not_session_edited(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    prepare_repository_with_unstaged_edit(repository_root)
    unrelated_path = repository_root / "unrelated.py"
    write_session_edits(temp_directory, _SESSION_ID, [unrelated_path.resolve()])
    completed_hook = run_hook(
        "git commit -m update", _SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_git_dash_c_form_resolves_repository(tmp_path: Path) -> None:
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    write_session_edits(temp_directory, _SESSION_ID, [tracked_file.resolve()])
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    completed_hook = run_hook(
        f'git -C "{repository_root}" commit -m update',
        _SESSION_ID,
        elsewhere,
        temp_directory,
        home_directory,
    )
    assert completed_hook.returncode == 0
    denial = parse_denial(completed_hook.stdout)
    assert denial["permissionDecision"] == "deny"
    assert "widget.py" in denial["permissionDecisionReason"]
