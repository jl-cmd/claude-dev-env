"""Behavioral tests for the git_tracking parts module."""

import os
import subprocess
from pathlib import Path

from tdd_enforcer_parts import git_tracking


def _git(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull},
    )


def _init_repository(repository_root: Path) -> None:
    _git(repository_root, "init", "-q")
    _git(repository_root, "config", "user.email", "test@example.com")
    _git(repository_root, "config", "user.name", "Test")
    _git(repository_root, "config", "commit.gpgsign", "false")


def test_absent_but_tracked_true_after_committed_file_removed(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    tracked = tmp_path / "service.py"
    tracked.write_text("def serve(): return 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    tracked.unlink()
    assert git_tracking.is_absent_but_tracked(tracked) is True


def test_absent_but_tracked_false_for_untracked_absent_file(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    assert git_tracking.is_absent_but_tracked(tmp_path / "ghost.py") is False


def test_absent_but_tracked_false_when_file_present(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    present = tmp_path / "present.py"
    present.write_text("def here(): return 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    assert git_tracking.is_absent_but_tracked(present) is False
