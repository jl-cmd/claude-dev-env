"""End-to-end tests for the absent-but-tracked restore exemption.

Drives the real ``tdd_enforcer.py`` entry hook over a Write payload in a temp
git repository, proving a remove-then-Write rewrite of committed code is allowed
even when the paired test's freshness window has lapsed, while new untracked
code and real edits to a present file stay gated.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent / "tdd_enforcer.py"
STALE_MTIME_OFFSET_SECONDS = 700
DISABLE_EPHEMERAL_ENVIRONMENT = {"CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT": "1"}


def _run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, **DISABLE_EPHEMERAL_ENVIRONMENT},
    )


def _write_payload(file_path: Path, content: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": str(file_path), "content": content}}


def _decision_from(completed: subprocess.CompletedProcess[str]) -> str | None:
    if not completed.stdout:
        return None
    hook_output = json.loads(completed.stdout).get("hookSpecificOutput", {})
    return hook_output.get("permissionDecision")


def _run_git(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull},
    )


def _init_git_repository(repository_root: Path) -> None:
    _run_git(repository_root, "init", "-q")
    _run_git(repository_root, "config", "user.email", "test@example.com")
    _run_git(repository_root, "config", "user.name", "Test")
    _run_git(repository_root, "config", "commit.gpgsign", "false")


def _commit_tracked_service(repository_root: Path) -> tuple[Path, Path]:
    production_file = repository_root / "service.py"
    production_file.write_text("def serve(): return 1\n")
    sibling_test = repository_root / "test_service.py"
    sibling_test.write_text("def test_serve(): pass\n")
    _run_git(repository_root, "add", "-A")
    _run_git(repository_root, "commit", "-q", "-m", "init")
    return production_file, sibling_test


def test_should_allow_restore_write_of_absent_but_tracked_file_despite_stale_window(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_git_repository(repository_root)
    production_file, sibling_test = _commit_tracked_service(repository_root)
    stale_timestamp = os.stat(sibling_test).st_mtime - STALE_MTIME_OFFSET_SECONDS
    os.utime(sibling_test, (stale_timestamp, stale_timestamp))
    production_file.unlink()

    completed = _run_hook(_write_payload(production_file, "def serve(): return 2\n"))

    assert _decision_from(completed) == "allow"


def test_should_still_deny_write_of_absent_untracked_file_without_fresh_test(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_git_repository(repository_root)
    untracked_file = repository_root / "brand_new.py"

    completed = _run_hook(_write_payload(untracked_file, "def fresh(): return 1\n"))

    assert _decision_from(completed) == "deny"


def test_should_still_deny_write_of_present_file_with_stale_test(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_git_repository(repository_root)
    production_file, sibling_test = _commit_tracked_service(repository_root)
    stale_timestamp = os.stat(sibling_test).st_mtime - STALE_MTIME_OFFSET_SECONDS
    os.utime(sibling_test, (stale_timestamp, stale_timestamp))

    completed = _run_hook(_write_payload(production_file, "def serve(): return 2\n"))

    assert _decision_from(completed) == "deny"
