from __future__ import annotations

import os
import subprocess
from pathlib import Path

import post_commit
import pytest


def build_fixture_git_environment() -> dict[str, str]:
    """Copy the process environment without inherited Git state overrides."""
    return {
        each_name: each_value
        for each_name, each_value in os.environ.items()
        if not each_name.upper().startswith("GIT_")
    }


def clear_inherited_git_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove inherited Git state overrides from the current test process."""
    for each_name in list(os.environ):
        if each_name.upper().startswith("GIT_"):
            monkeypatch.delenv(each_name, raising=False)


def test_fixture_git_environment_preserves_process_execution_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fixture environment keeps PATH while removing Git overrides."""
    monkeypatch.setenv("PATH", "fixture-execution-path")
    monkeypatch.setenv("GIT_DIR", "unrelated-repository")

    fixture_environment = build_fixture_git_environment()

    assert fixture_environment["PATH"] == "fixture-execution-path"
    assert all(not each_name.upper().startswith("GIT_") for each_name in fixture_environment)


def run_fixture_git(repository_path: Path, *arguments: str) -> str:
    """Run Git in a fixture repository and return standard output."""
    completed_process = subprocess.run(
        ["git", *arguments],
        cwd=repository_path,
        check=False,
        capture_output=True,
        text=True,
        env=build_fixture_git_environment(),
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
    run_fixture_git(repository_path, "config", "commit.gpgsign", "false")
    fixture_hooks_directory = repository_path / ".fixture-hooks"
    fixture_hooks_directory.mkdir(exist_ok=True)
    run_fixture_git(
        repository_path,
        "config",
        "core.hooksPath",
        str(fixture_hooks_directory),
    )


def initialize_fixture_repository(repository_path: Path) -> None:
    """Create and configure a fixture Git repository."""
    repository_path.mkdir()
    run_fixture_git(repository_path, "init", "-b", "main")
    configure_fixture_identity(repository_path)


def test_native_submodule_commit_records_parent_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real submodule commit creates the matching parent pointer commit."""
    unrelated_repository = tmp_path / "unrelated-repository"
    initialize_fixture_repository(unrelated_repository)
    monkeypatch.setenv("GIT_DIR", str(unrelated_repository / ".git"))

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
        "nested/sub[module]",
    )
    run_fixture_git(parent_repository, "commit", "-am", "Add fixture submodule")

    submodule_repository = parent_repository / "nested" / "sub[module]"
    configure_fixture_identity(submodule_repository)
    (parent_repository / "staged-note.txt").write_text("keep staged\n", encoding="utf-8")
    run_fixture_git(parent_repository, "add", "staged-note.txt")
    (submodule_repository / "change.txt").write_text("fixture change\n", encoding="utf-8")
    run_fixture_git(submodule_repository, "add", "change.txt")
    run_fixture_git(submodule_repository, "commit", "-m", "Record fixture change")
    original_working_directory = Path.cwd()
    try:
        clear_inherited_git_environment(monkeypatch)
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
        "HEAD:nested/sub[module]",
    )

    assert recorded_pointer_hash == submodule_commit_hash
    assert parent_commit_subject == (
        f"chore: update sub[module] submodule to {submodule_commit_hash}"
    )
    assert "Submodule commit: Record fixture change" in parent_commit_body
    assert run_fixture_git(parent_repository, "status", "--short") == "A  staged-note.txt"


def test_parent_update_returns_git_diagnostic_for_failed_add(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed parent add returns the Git diagnostic and literal pathspec."""
    parent_repository = tmp_path / "parent-repository"
    submodule_repository = parent_repository / "sub[module]"
    submodule_repository.mkdir(parents=True)
    recorded_commands: list[tuple[str, ...]] = []

    def fail_git_add(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        recorded_commands.append(arguments)
        return subprocess.CompletedProcess(
            ["git", *arguments],
            1,
            "",
            "fatal: fixture add failure",
        )

    monkeypatch.setattr(post_commit, "execute_git", fail_git_add)

    parent_update = post_commit.update_parent_pointer(
        parent_repository,
        submodule_repository,
        "a" * 40,
        "Fixture commit",
    )

    assert parent_update == (
        post_commit.ParentPointerStatus.FAILED,
        "fatal: fixture add failure",
    )
    assert recorded_commands == [("add", "--", ":(literal)sub[module]")]


def test_main_prints_git_failure_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The hook prints the Git diagnostic when the parent update fails."""
    submodule_repository = tmp_path / "submodule"
    parent_repository = tmp_path / "parent"
    submodule_repository.mkdir()
    parent_repository.mkdir()
    monkeypatch.setattr(
        post_commit,
        "run_git_from_current_directory",
        lambda *arguments: str(submodule_repository),
    )
    monkeypatch.setattr(post_commit, "find_parent_repo", lambda repo: parent_repository)
    monkeypatch.setattr(post_commit, "run_git", lambda *arguments, cwd: "a" * 40)
    monkeypatch.setattr(
        post_commit,
        "update_parent_pointer",
        lambda *arguments: (
            post_commit.ParentPointerStatus.FAILED,
            "fatal: fixture commit failure",
        ),
    )

    assert post_commit.main() == 0
    assert "Git diagnostic: fatal: fixture commit failure" in capsys.readouterr().out
