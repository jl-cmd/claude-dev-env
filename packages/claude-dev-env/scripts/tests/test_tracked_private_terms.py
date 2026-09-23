"""Behavior tests for the tracked private-term check."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from dev_env_scripts_constants.private_term_constants import PrivateTermDigest
from repository_checks import tracked_private_terms
from repository_checks.config.constants import (
    CHECK_ID_TRACKED_PRIVATE_TERMS,
    FINDINGS_EXIT_CODE,
    SUCCESS_EXIT_CODE,
)

_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_policy_test_support import (
    commit_tracked_files,
    initialize_repository,
    run_policy,
    write_text,
)

_FIXTURE_TERM = "acmewidget"


@pytest.fixture(autouse=True)
def private_fixture_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tracked_private_terms,
        "ALL_PRIVATE_TERM_DIGESTS",
        frozenset(
            {
                PrivateTermDigest(
                    length=len(_FIXTURE_TERM),
                    sha256=hashlib.sha256(_FIXTURE_TERM.encode("utf-8")).hexdigest(),
                )
            }
        ),
    )


def test_should_flag_a_tracked_file_naming_a_private_organization(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    write_text(repository_root / "docs" / "notes.md", "intro\nBuilt by Acme Widgets.\n")
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert f"{CHECK_ID_TRACKED_PRIVATE_TERMS}: docs/notes.md:" in stdout_text
    assert "Line 2" in stdout_text
    assert "Acme" not in stdout_text


def test_should_skip_a_changelog_that_names_a_private_organization(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    write_text(
        repository_root / "packages" / "tool" / "CHANGELOG.md",
        "* Built by Acme Widgets.\n",
    )
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == SUCCESS_EXIT_CODE
    assert stdout_text == ""


def test_should_pass_a_tree_that_names_no_private_organization(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    write_text(repository_root / "docs" / "notes.md", "An acme of widget design.\n")
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == SUCCESS_EXIT_CODE
    assert stdout_text == ""


def test_should_pass_a_repository_the_named_organization_owns(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/AcmeWidget/app.git"],
        cwd=repository_root,
        check=True,
    )
    write_text(repository_root / "docs" / "notes.md", "Built by Acme Widgets.\n")
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == SUCCESS_EXIT_CODE
    assert stdout_text == ""


def test_should_flag_a_repository_another_owner_holds(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/someone/app.git"],
        cwd=repository_root,
        check=True,
    )
    write_text(repository_root / "docs" / "notes.md", "Built by Acme Widgets.\n")
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert f"{CHECK_ID_TRACKED_PRIVATE_TERMS}: docs/notes.md:" in stdout_text
