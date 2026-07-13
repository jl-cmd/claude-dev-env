"""Behavioral tests for the git_blob_readers parts module."""

import subprocess
from pathlib import Path

from code_rules_gate_parts import git_blob_readers, git_file_sets


def _run(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        env=git_file_sets.repository_environment(),
    )


def _init_repository(repository_root: Path) -> None:
    _run(repository_root, "init", "--initial-branch=main")
    _run(repository_root, "config", "user.email", "test@example.com")
    _run(repository_root, "config", "user.name", "Test")
    _run(repository_root, "config", "commit.gpgsign", "false")
    disabled_hooks = repository_root / "disabled-git-hooks"
    disabled_hooks.mkdir()
    _run(repository_root, "config", "core.hooksPath", str(disabled_hooks))
    (repository_root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "seed")


def test_read_prior_committed_content_returns_head_blob(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "tracked.py").write_text("value = 1\n", encoding="utf-8")
    _run(repository_root, "add", "tracked.py")
    _run(repository_root, "commit", "-m", "add tracked")

    content = git_blob_readers.read_prior_committed_content(repository_root, "tracked.py")

    assert content == "value = 1\n"


def test_read_prior_committed_content_returns_empty_for_untracked(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)

    assert git_blob_readers.read_prior_committed_content(repository_root, "absent.py") == ""


def test_read_staged_content_returns_none_when_not_staged(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)

    assert git_blob_readers.read_staged_content(repository_root, "absent.py") is None


def test_staged_blob_exists_reflects_index_presence(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "staged.py").write_text("value = 2\n", encoding="utf-8")
    _run(repository_root, "add", "staged.py")

    assert git_blob_readers.staged_blob_exists(repository_root, "staged.py")
    assert not git_blob_readers.staged_blob_exists(repository_root, "absent.py")
