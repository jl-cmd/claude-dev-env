"""Behavior tests for committed pytest testpaths."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_checks.config.constants import (
    CHECK_ID_PYTEST_TESTPATHS,
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


def test_should_flag_a_pytest_testpath_discovery_miss(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    package_root = repository_root / "shared_utils"
    _write_pytest_configuration(package_root)
    write_text(
        package_root / "theme_assets" / "tests" / "test_palette.py",
        "def test_palette() -> None:\n    assert True\n",
    )
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert CHECK_ID_PYTEST_TESTPATHS in stdout_text
    assert "shared_utils/theme_assets/tests/test_palette.py" in stdout_text


def test_should_fail_closed_when_pytest_config_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    _write_pytest_configuration(repository_root / "shared_utils")
    commit_tracked_files(repository_root)
    patch_unreadable_named_file(monkeypatch, "pyproject.toml", "pyproject unreadable")
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FAILED_CHECK_EXIT_CODE
    assert CHECK_ID_PYTEST_TESTPATHS in stdout_text
    assert "error: rule failed:" in stdout_text


def _write_pytest_configuration(package_root: Path) -> None:
    write_text(
        package_root / "pyproject.toml",
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
    )
    write_text(
        package_root / "tests" / "test_root_behavior.py",
        "def test_ok() -> None:\n    assert True\n",
    )
