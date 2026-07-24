"""Behavioral tests for the git_blob_readers parts module."""

import subprocess
from pathlib import Path

import pytest
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


def test_read_prior_committed_contents_batch_returns_empty_for_missing_head(
    tmp_path: Path,
) -> None:
    """A new path with no HEAD blob maps to "" via the in-stream missing marker."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "brand_new.py").write_text("fresh = 1\n", encoding="utf-8")
    _run(repository_root, "add", "brand_new.py")

    content_by_relative_path = git_blob_readers.read_prior_committed_contents_batch(
        repository_root, ["brand_new.py", "also_absent.py"]
    )

    assert content_by_relative_path["brand_new.py"] == ""
    assert content_by_relative_path["also_absent.py"] == ""
    assert git_blob_readers.read_prior_committed_content(
        repository_root, "brand_new.py"
    ) == content_by_relative_path["brand_new.py"]


def test_read_prior_committed_contents_batch_returns_present_head_blob(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "tracked.py").write_text("value = 1\n", encoding="utf-8")
    _run(repository_root, "add", "tracked.py")
    _run(repository_root, "commit", "-m", "add tracked")

    content_by_relative_path = git_blob_readers.read_prior_committed_contents_batch(
        repository_root, ["tracked.py"]
    )

    assert content_by_relative_path["tracked.py"] == "value = 1\n"
    assert content_by_relative_path["tracked.py"] == (
        git_blob_readers.read_prior_committed_content(repository_root, "tracked.py")
    )


def test_read_staged_contents_batch_returns_none_for_non_utf8_blob(
    tmp_path: Path,
) -> None:
    """A staged binary blob maps to None without failing the whole batch."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "text.py").write_text("ok = 1\n", encoding="utf-8")
    (repository_root / "binary.dat").write_bytes(b"\xff\xfe\x00\x01 not utf-8")
    _run(repository_root, "add", "text.py", "binary.dat")

    content_by_relative_path = git_blob_readers.read_staged_contents_batch(
        repository_root, ["text.py", "binary.dat", "absent.py"]
    )

    assert content_by_relative_path["binary.dat"] is None
    assert content_by_relative_path["absent.py"] is None
    assert git_blob_readers.read_staged_content(repository_root, "binary.dat") is None
    assert content_by_relative_path["text.py"] == git_blob_readers.read_staged_content(
        repository_root, "text.py"
    )
    assert content_by_relative_path["text.py"] is not None


def test_read_prior_committed_contents_batch_issues_one_git_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One batch call covers every path; the per-file reader is not invoked."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "alpha.py").write_text("alpha = 1\n", encoding="utf-8")
    (repository_root / "beta.py").write_text("beta = 2\n", encoding="utf-8")
    _run(repository_root, "add", "alpha.py", "beta.py")
    _run(repository_root, "commit", "-m", "add pair")

    real_run = subprocess.run
    batch_call_count = [0]

    def counting_run(*arguments: object, **keyword_arguments: object) -> object:
        command = arguments[0] if arguments else keyword_arguments.get("args")
        if (
            isinstance(command, (list, tuple))
            and len(command) >= 3
            and command[0] == "git"
            and command[1] == "cat-file"
            and command[2] == "--batch"
        ):
            batch_call_count[0] += 1
        return real_run(*arguments, **keyword_arguments)

    monkeypatch.setattr(subprocess, "run", counting_run)

    content_by_relative_path = git_blob_readers.read_prior_committed_contents_batch(
        repository_root, ["alpha.py", "beta.py"]
    )

    assert batch_call_count[0] == 1
    assert content_by_relative_path["alpha.py"] == "alpha = 1\n"
    assert content_by_relative_path["beta.py"] == "beta = 2\n"
