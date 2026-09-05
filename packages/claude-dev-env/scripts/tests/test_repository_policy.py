"""Command behavior for the committed-tree repository checker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

import repository_policy
from repository_checks.config.constants import (
    CHECK_ID_CLAUDE_MD_ORPHANS,
    CHECK_ID_ENV_VAR_DOCUMENTATION,
    CHECK_ID_PACKAGE_INVENTORY,
    CHECK_ID_PYTEST_TESTPATHS,
    CHECK_ID_TRACKED_PERSONAL_DATA,
)
from repository_policy_test_support import run_policy, seed_clean_repository

_POLICY_SCRIPT_PATH = _SCRIPTS_DIRECTORY / "repository_policy.py"
_CHECK_SCRIPT_PATH = _SCRIPTS_DIRECTORY / "check.ps1"
_UTF8_ENCODING = "utf-8"


def test_should_exit_zero_on_a_clean_tracked_tree(tmp_path: Path) -> None:
    repository_root = seed_clean_repository(tmp_path / "repo")
    exit_code, stdout_text, stderr_text = run_policy(repository_root)
    assert exit_code == 0
    assert stdout_text == ""
    assert stderr_text == ""


def test_should_keep_stable_check_identifiers() -> None:
    assert repository_policy.ALL_CHECK_IDS == (
        CHECK_ID_CLAUDE_MD_ORPHANS,
        CHECK_ID_ENV_VAR_DOCUMENTATION,
        CHECK_ID_PACKAGE_INVENTORY,
        CHECK_ID_PYTEST_TESTPATHS,
        CHECK_ID_TRACKED_PERSONAL_DATA,
    )


def test_should_invoke_the_checker_from_check_script() -> None:
    script_text = _CHECK_SCRIPT_PATH.read_text(encoding=_UTF8_ENCODING)
    assert "Invoke-Tool -Label 'repository-policy'" in script_text
    assert "repository_policy.py" in script_text
    assert "--repository-root" in script_text
    assert "SkipRepositoryPolicy" in script_text


def test_should_run_the_checker_as_a_subprocess(tmp_path: Path) -> None:
    repository_root = seed_clean_repository(tmp_path / "repo")
    completed = subprocess.run(
        [
            sys.executable,
            str(_POLICY_SCRIPT_PATH),
            "--repository-root",
            str(repository_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout == ""
