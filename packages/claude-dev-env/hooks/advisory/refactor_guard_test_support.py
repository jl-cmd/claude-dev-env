"""Shared temporary-repository support for refactor guard tests."""

from __future__ import annotations

import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def git_repository(tmp_path: Path) -> Generator[Path]:
    """Create a committed temporary repository for refactor guard tests."""
    repository_path = tmp_path / "repository"
    repository_path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository_path, check=True)
    yield repository_path


def commit_file(repository_path: Path, file_path: Path, file_content: str) -> None:
    """Write and commit one file in a temporary repository."""
    file_path.write_text(file_content, encoding="utf-8")
    subprocess.run(["git", "add", str(file_path)], cwd=repository_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Refactor Guard Test",
            "-c",
            "user.email=refactor-guard@example.invalid",
            "commit",
            "-q",
            "-m",
            "baseline",
            "--no-verify",
        ],
        cwd=repository_path,
        check=True,
    )


def stage_file(repository_path: Path, file_path: Path, file_content: str) -> None:
    """Write and stage one file in a temporary repository."""
    file_path.write_text(file_content, encoding="utf-8")
    subprocess.run(["git", "add", str(file_path)], cwd=repository_path, check=True)
