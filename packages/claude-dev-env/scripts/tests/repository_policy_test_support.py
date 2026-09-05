"""Shared fixtures for repository-policy behavior tests."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
UTF8_ENCODING = "utf-8"

if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import repository_policy


def initialize_repository(repository_root: Path) -> None:
    repository_root.mkdir(parents=True, exist_ok=True)
    run_git(repository_root, ("init", "--initial-branch=main"))


def commit_tracked_files(repository_root: Path) -> None:
    run_git(repository_root, ("add", "-A"))
    run_git(repository_root, ("commit", "--quiet", "-m", "seed"))


def write_text(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding=UTF8_ENCODING)


def patch_unreadable_named_file(
    monkeypatch: pytest.MonkeyPatch, filename: str, error_text: str
) -> None:
    original_read_text = Path.read_text

    def refuse_named_file(
        file_path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        if file_path.name == filename:
            raise OSError(error_text)
        return original_read_text(file_path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", refuse_named_file)


def seed_clean_repository(repository_root: Path) -> Path:
    initialize_repository(repository_root)
    write_text(repository_root / "README.md", "clean tree\n")
    commit_tracked_files(repository_root)
    return repository_root


def run_policy(
    repository_root: Path, all_arguments: list[str] | None = None
) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = repository_policy.main(
        all_arguments or [],
        repository_root=repository_root,
        stdout=stdout,
        stderr=stderr,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue()


def run_git(repository_root: Path, all_arguments: tuple[str, ...]) -> None:
    subprocess.run(
        (
            "git",
            "-c",
            "user.email=ci@example.com",
            "-c",
            "user.name=CI",
            "-c",
            "core.hooksPath=",
            *all_arguments,
        ),
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
