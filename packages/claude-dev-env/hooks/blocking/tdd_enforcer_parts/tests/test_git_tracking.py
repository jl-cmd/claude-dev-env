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


def test_has_uncommitted_change_from_head_true_for_untracked_file(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    untracked = tmp_path / "test_orders.py"
    untracked.write_text("def test_fulfill(): pass\n")
    assert git_tracking.has_uncommitted_change_from_head(untracked) is True


def test_has_uncommitted_change_from_head_true_for_tracked_modified_file(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    tracked = tmp_path / "test_orders.py"
    tracked.write_text("def test_fulfill(): pass\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    tracked.write_text("def test_fulfill(): assert True\n")
    assert git_tracking.has_uncommitted_change_from_head(tracked) is True


def test_has_uncommitted_change_from_head_false_for_tracked_clean_file(tmp_path: Path) -> None:
    _init_repository(tmp_path)
    tracked = tmp_path / "test_orders.py"
    tracked.write_text("def test_fulfill(): pass\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    tracked.touch()
    assert git_tracking.has_uncommitted_change_from_head(tracked) is False


def test_has_uncommitted_change_from_head_true_outside_a_git_repository(tmp_path: Path) -> None:
    stray = tmp_path / "test_orders.py"
    stray.write_text("def test_fulfill(): pass\n")
    assert git_tracking.has_uncommitted_change_from_head(stray) is True


def test_has_uncommitted_change_from_head_true_for_staged_new_file_never_committed(
    tmp_path: Path,
) -> None:
    """A brand-new file only ``git add``-ed carries content HEAD never had.

    Regression guard: comparing the working tree to the index (rather than to
    HEAD) reads a freshly staged file as unchanged, since staging makes the
    index match the working tree exactly. That misses every staged-but-never-
    committed file, which is exactly how a RED-step test file is staged.
    """
    _init_repository(tmp_path)
    _git(tmp_path, "commit", "--allow-empty", "-q", "-m", "baseline")
    staged_new_test = tmp_path / "test_orders.py"
    staged_new_test.write_text("def test_fulfill(): pass\n")
    _git(tmp_path, "add", "-A")
    assert git_tracking.has_uncommitted_change_from_head(staged_new_test) is True


def test_has_uncommitted_change_from_head_true_for_staged_modification(tmp_path: Path) -> None:
    """A tracked test's staged edit still differs from HEAD, not only the index."""
    _init_repository(tmp_path)
    tracked = tmp_path / "test_orders.py"
    tracked.write_text("def test_fulfill(): pass\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    tracked.write_text("def test_fulfill(): assert True\n")
    _git(tmp_path, "add", "-A")
    assert git_tracking.has_uncommitted_change_from_head(tracked) is True
