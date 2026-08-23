"""Tests for refactor candidate eligibility against a temporary Git repository."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

ADVISORY_DIRECTORY = Path(__file__).resolve().parent
if str(ADVISORY_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(ADVISORY_DIRECTORY))

import refactor_guard  # noqa: E402


@pytest.fixture
def git_repository(tmp_path: Path) -> Generator[Path]:
    """Create a committed temporary repository for changed-surface checks."""
    repository_path = tmp_path / "repository"
    repository_path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository_path, check=True)
    yield repository_path


def _commit_file(repository_path: Path, file_path: Path, file_content: str) -> None:
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


def _stage_file(repository_path: Path, file_path: Path, file_content: str) -> None:
    file_path.write_text(file_content, encoding="utf-8")
    subprocess.run(["git", "add", str(file_path)], cwd=repository_path, check=True)


def test_refactor_candidate_is_eligible_when_old_lines_are_outside_changed_surface(
    git_repository: Path,
) -> None:
    source_path = git_repository / "module.py"
    _commit_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n",
    )
    _stage_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount + 1\n",
    )

    old_function = "def calculate_total(amount: int) -> int:\n    return amount"
    renamed_function = "def compute_total(amount: int) -> int:\n    return amount"

    assert refactor_guard.is_refactor_eligible(str(source_path), old_function, renamed_function)


def test_refactor_candidate_is_ineligible_when_old_lines_are_in_changed_surface(
    git_repository: Path,
) -> None:
    source_path = git_repository / "module.py"
    _commit_file(git_repository, source_path, "pass\n")
    old_function = "def calculate_total(amount: int) -> int:\n    return amount"
    _stage_file(git_repository, source_path, f"{old_function}\n")
    renamed_function = "def compute_total(amount: int) -> int:\n    return amount"

    assert not refactor_guard.is_refactor_eligible(str(source_path), old_function, renamed_function)


def test_changed_surface_reads_staged_and_unstaged_lines(git_repository: Path) -> None:
    source_path = git_repository / "module.py"
    _commit_file(git_repository, source_path, "baseline = 1\n")

    _stage_file(git_repository, source_path, "staged_line = 1\n")
    source_path.write_text("unstaged_line = 1\n", encoding="utf-8")

    all_added_lines = refactor_guard.get_git_diff_added_lines(str(source_path))

    assert all_added_lines == {"staged_line = 1", "unstaged_line = 1"}


def test_ordinary_edit_is_not_a_refactor_candidate(git_repository: Path) -> None:
    source_path = git_repository / "module.py"
    _commit_file(git_repository, source_path, "return_amount = 1\n")

    assert not refactor_guard.is_refactor_eligible(
        str(source_path), "return_amount = 1", "return_amount = 2"
    )


def test_new_file_is_not_a_refactor_candidate(git_repository: Path) -> None:
    source_path = git_repository / "new_module.py"
    source_path.write_text(
        "def calculate_total(amount: int) -> int:\n    return amount\n",
        encoding="utf-8",
    )

    assert refactor_guard.is_new_file(str(source_path))
    assert not refactor_guard.is_refactor_eligible(
        str(source_path),
        "def calculate_total(amount: int) -> int:\n    return amount",
        "def compute_total(amount: int) -> int:\n    return amount",
    )


def test_hook_infrastructure_is_not_a_refactor_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    hook_path = str(Path.home() / ".claude" / "settings.json")

    assert refactor_guard.is_hook_infrastructure(hook_path)
    assert not refactor_guard.is_refactor_eligible(
        hook_path,
        "def calculate_total(amount: int) -> int:\n    return amount",
        "def compute_total(amount: int) -> int:\n    return amount",
    )
