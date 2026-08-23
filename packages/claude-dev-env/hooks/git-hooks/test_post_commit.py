from __future__ import annotations

import os
import subprocess
from pathlib import Path

import post_commit


def run_fixture_git(repository_path: Path, *arguments: str) -> str:
    """Run Git in a fixture repository and return standard output."""
    completed_process = subprocess.run(
        ["git", *arguments],
        cwd=repository_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed_process.returncode == 0, completed_process.stderr
    return completed_process.stdout.strip()


def configure_fixture_identity(repository_path: Path) -> None:
    """Configure a stable identity for a fixture repository."""
    run_fixture_git(repository_path, "config", "user.name", "Fixture User")
    run_fixture_git(
        repository_path,
        "config",
        "user.email",
        "fixture@example.invalid",
    )


def initialize_fixture_repository(repository_path: Path) -> None:
    """Create and configure a fixture Git repository."""
    repository_path.mkdir()
    run_fixture_git(repository_path, "init", "-b", "main")
    configure_fixture_identity(repository_path)


def test_native_submodule_commit_records_parent_pointer(
    tmp_path: Path,
) -> None:
    """A real submodule commit creates the matching parent pointer commit."""
    source_repository = tmp_path / "source-repository"
    parent_repository = tmp_path / "parent-repository"
    initialize_fixture_repository(source_repository)
    (source_repository / "README.md").write_text("fixture source\n", encoding="utf-8")
    run_fixture_git(source_repository, "add", "README.md")
    run_fixture_git(source_repository, "commit", "-m", "Create fixture source")

    initialize_fixture_repository(parent_repository)
    (parent_repository / "README.md").write_text("fixture parent\n", encoding="utf-8")
    run_fixture_git(parent_repository, "add", "README.md")
    run_fixture_git(parent_repository, "commit", "-m", "Create fixture parent")
    run_fixture_git(
        parent_repository,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(source_repository),
        "nested/submodule",
    )
    run_fixture_git(parent_repository, "commit", "-am", "Add fixture submodule")

    submodule_repository = parent_repository / "nested" / "submodule"
    configure_fixture_identity(submodule_repository)
    (parent_repository / "staged-note.txt").write_text("keep staged\n", encoding="utf-8")
    run_fixture_git(parent_repository, "add", "staged-note.txt")
    (submodule_repository / "change.txt").write_text("fixture change\n", encoding="utf-8")
    run_fixture_git(submodule_repository, "add", "change.txt")
    run_fixture_git(submodule_repository, "commit", "-m", "Record fixture change")
    original_working_directory = Path.cwd()
    try:
        os.chdir(submodule_repository)
        assert post_commit.main() == 0
    finally:
        os.chdir(original_working_directory)

    submodule_commit_hash = run_fixture_git(submodule_repository, "rev-parse", "HEAD")
    parent_commit_subject = run_fixture_git(parent_repository, "log", "-1", "--pretty=%s")
    parent_commit_body = run_fixture_git(parent_repository, "log", "-1", "--pretty=%B")
    recorded_pointer_hash = run_fixture_git(
        parent_repository,
        "rev-parse",
        "HEAD:nested/submodule",
    )

    assert recorded_pointer_hash == submodule_commit_hash
    assert parent_commit_subject == (
        f"chore: update submodule submodule to {submodule_commit_hash}"
    )
    assert "Submodule commit: Record fixture change" in parent_commit_body
    assert run_fixture_git(parent_repository, "status", "--short") == "A  staged-note.txt"
