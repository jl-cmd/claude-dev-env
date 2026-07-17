"""Behavioral tests for the verified-commit gate's deny-reason resolution."""

import subprocess
from pathlib import Path

from verified_commit_gate_parts.deny_reason import deny_reason_for_directory


def _run_git(work_dir: Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(work_dir), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo_with_no_upstream(tmp_path: Path) -> Path:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _run_git(work_dir, "init", "--initial-branch=main")
    _run_git(work_dir, "config", "user.email", "tests@example.com")
    _run_git(work_dir, "config", "user.name", "Gate Tests")
    (work_dir / "app.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left + right\n", encoding="utf-8"
    )
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-m", "base")
    return work_dir


def test_deny_reason_for_directory_none_when_not_a_git_repo(tmp_path: Path) -> None:
    assert deny_reason_for_directory(str(tmp_path), "") is None


def test_deny_reason_for_directory_none_with_no_resolvable_upstream(tmp_path: Path) -> None:
    work_dir = _make_repo_with_no_upstream(tmp_path)
    assert deny_reason_for_directory(str(work_dir), "") is None
