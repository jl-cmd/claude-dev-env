"""Shared real-git-repository builders for the code_rules_gate_parts test suite.

Every helper drives a real ``git`` subprocess against a throwaway repository
under ``tmp_path`` — no mocked git state — so a test proves the module works
against the same git plumbing the live commit hook runs against.
"""

import subprocess
from pathlib import Path

from code_rules_gate_parts import git_file_sets


def run_git(repository_root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    """Run one git subcommand in *repository_root* and raise on failure."""
    return subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        env=git_file_sets.repository_environment(),
    )


def init_repository(repository_root: Path) -> None:
    """Initialize *repository_root* as a git repo with one seed commit."""
    run_git(repository_root, "init", "--initial-branch=main")
    run_git(repository_root, "config", "user.email", "test@example.com")
    run_git(repository_root, "config", "user.name", "Test")
    run_git(repository_root, "config", "commit.gpgsign", "false")
    (repository_root / "seed.txt").write_text("seed\n", encoding="utf-8")
    run_git(repository_root, "add", "-A")
    run_git(repository_root, "commit", "--no-verify", "-m", "seed")


def write_and_stage(repository_root: Path, relative_path: str, file_text: str) -> Path:
    """Write *file_text* to *relative_path* under *repository_root* and stage it."""
    file_path = repository_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(file_text, encoding="utf-8")
    run_git(repository_root, "add", "--", relative_path)
    return file_path


def write_commit_and_stage_change(
    repository_root: Path, relative_path: str, committed_text: str, staged_text: str
) -> Path:
    """Commit *committed_text* at *relative_path*, then overwrite and stage *staged_text*.

    Builds the shape a regression check compares: real history at HEAD (what
    the baseline run sees), then a staged edit on top of it (what the staged
    run sees).
    """
    file_path = write_and_stage(repository_root, relative_path, committed_text)
    run_git(repository_root, "commit", "--no-verify", "-m", f"seed {relative_path}")
    file_path.write_text(staged_text, encoding="utf-8")
    run_git(repository_root, "add", "--", relative_path)
    return file_path


def repository_with_root_pytest_config(tmp_path: Path) -> Path:
    """Return a fresh repo under *tmp_path* with a root-level ``pytest.ini`` committed."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    init_repository(repository_root)
    (repository_root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    run_git(repository_root, "add", "-A")
    run_git(repository_root, "commit", "--no-verify", "-m", "add pytest.ini")
    return repository_root
