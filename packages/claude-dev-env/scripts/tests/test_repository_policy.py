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
    FOLLOWUP_LEDGER_MODULE_NAME,
    SUCCESS_EXIT_CODE,
)
from repository_checks.hook_modules import load_hooks_module
from repository_policy_test_support import (
    commit_tracked_files,
    initialize_repository,
    run_policy,
    seed_clean_repository,
    write_text,
)

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


def test_should_record_a_stale_inventory_and_leave_the_tree_passing(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    package_directory = repository_root / "pipeline"
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
    commit_tracked_files(repository_root)

    exit_code, stdout_text, _stderr_text = run_policy(repository_root)

    assert exit_code == SUCCESS_EXIT_CODE
    assert stdout_text == (
        "advisory: package-inventory: pipeline/check_dialer_seam_cli.py: "
        "production file is absent from package inventory\n"
    )
    ledger = load_hooks_module(FOLLOWUP_LEDGER_MODULE_NAME)
    all_recorded = ledger.all_recorded_findings(repository_root)
    assert [each_finding.message for each_finding in all_recorded] == [
        "production file is absent from package inventory"
    ]
