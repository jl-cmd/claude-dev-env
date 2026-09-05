"""Behavior tests for committed package inventories."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_checks.config.constants import (
    CHECK_ID_PACKAGE_INVENTORY,
    FAILED_CHECK_EXIT_CODE,
    FINDINGS_EXIT_CODE,
)
from repository_policy_test_support import (
    commit_tracked_files,
    initialize_repository,
    patch_unreadable_named_file,
    run_policy,
    write_text,
)

_SKILL_INVENTORY_MARKDOWN = (
    "# Skill\n\n"
    "| File | Role |\n"
    "|---|---|\n"
    "| `listed_alpha.py` | Alpha helper |\n"
    "| `listed_beta.py` | Beta helper |\n"
)


def test_should_flag_a_stale_package_inventory(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    package_directory = repository_root / "pipeline"
    _write_package_inventory(package_directory)
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert CHECK_ID_PACKAGE_INVENTORY in stdout_text
    assert "pipeline/check_dialer_seam_cli.py" in stdout_text


def test_should_check_active_skills_and_exclude_archived_skills(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    _seed_skill_package(repository_root / ".agents" / "skills" / "live-skill")
    _seed_skill_package(repository_root / ".agents" / "skills-archived" / "old-skill")
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert CHECK_ID_PACKAGE_INVENTORY in stdout_text
    assert ".agents/skills/live-skill/scripts/unlisted_gamma.py" in stdout_text
    assert (
        ".agents/skills-archived/old-skill/scripts/unlisted_gamma.py" not in stdout_text
    )


def test_should_fail_closed_when_a_package_inventory_document_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    _write_package_inventory(repository_root / "pipeline")
    commit_tracked_files(repository_root)
    patch_unreadable_named_file(monkeypatch, "README.md", "inventory unreadable")
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FAILED_CHECK_EXIT_CODE
    assert CHECK_ID_PACKAGE_INVENTORY in stdout_text
    assert "error: rule failed:" in stdout_text


def _write_package_inventory(package_directory: Path) -> None:
    write_text(
        package_directory / "README.md",
        "# Pipeline\n\n"
        "| Path | Role |\n"
        "|---|---|\n"
        "| `dialer_compose.py` | Composes a dialer strip. |\n"
        "| `compose_dialer_cli.py` | CLI for the dialer strip. |\n",
    )
    write_text(package_directory / "dialer_compose.py", "x = 1\n")
    write_text(package_directory / "compose_dialer_cli.py", "x = 1\n")
    write_text(package_directory / "check_dialer_seam_cli.py", "x = 1\n")


def _seed_skill_package(skill_root: Path) -> None:
    write_text(skill_root / "SKILL.md", _SKILL_INVENTORY_MARKDOWN)
    scripts_directory = skill_root / "scripts"
    write_text(scripts_directory / "listed_alpha.py", "x = 1\n")
    write_text(scripts_directory / "listed_beta.py", "x = 1\n")
    write_text(scripts_directory / "unlisted_gamma.py", "x = 1\n")
