"""Behavior tests for tracked repository path discovery."""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_checks.tracked_tree import tracked_relative_paths
from repository_policy_test_support import run_policy, seed_clean_repository, write_text


def test_should_list_only_committed_relative_paths(tmp_path: Path) -> None:
    repository_root = seed_clean_repository(tmp_path / "repo")
    write_text(repository_root / "untracked.txt", "not committed\n")
    assert tracked_relative_paths(repository_root) == ("README.md",)


def test_should_skip_a_tracked_path_absent_from_the_worktree(tmp_path: Path) -> None:
    repository_root = seed_clean_repository(tmp_path / "repo")
    (repository_root / "README.md").unlink()
    exit_code, stdout_text, stderr_text = run_policy(repository_root)
    assert exit_code == 0
    assert stdout_text == ""
    assert stderr_text == ""
