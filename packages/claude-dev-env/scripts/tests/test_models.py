"""Behavior tests for the severity that decides the committed-tree gate."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_checks.config.constants import (
    ALL_CHECK_IDS,
    CHECK_ID_CLAUDE_MD_ORPHANS,
    CHECK_ID_PACKAGE_INVENTORY,
    FAILED_CHECK_EXIT_CODE,
    FINDINGS_EXIT_CODE,
    SEVERITY_BREAKING,
    SEVERITY_BY_CHECK_ID,
    SEVERITY_SMELL,
    SUCCESS_EXIT_CODE,
)
from repository_checks.hook_modules import load_hooks_module
from repository_checks.models import (
    RepositoryCheckReport,
    RepositoryFinding,
    severity_for_check_id,
)

_LEDGER_CONSTANTS_MODULE_NAME = "hooks_constants.followup_ledger_constants"


def test_should_choose_exit_code_by_report_severity() -> None:
    finding = RepositoryFinding("check", "file.py", "message")
    assert RepositoryCheckReport((), ()).exit_code == SUCCESS_EXIT_CODE
    assert RepositoryCheckReport((finding,), ()).exit_code == FINDINGS_EXIT_CODE
    assert RepositoryCheckReport((finding,), ("check",)).exit_code == (
        FAILED_CHECK_EXIT_CODE
    )


def test_should_declare_a_severity_for_every_check() -> None:
    assert tuple(SEVERITY_BY_CHECK_ID) == ALL_CHECK_IDS


def test_should_read_a_check_with_no_row_as_breaking() -> None:
    assert severity_for_check_id("check-with-no-row") == SEVERITY_BREAKING


def test_should_carry_the_ledger_severity_names() -> None:
    ledger_constants = load_hooks_module(_LEDGER_CONSTANTS_MODULE_NAME)
    assert SEVERITY_BREAKING == ledger_constants.SEVERITY_BREAKING
    assert SEVERITY_SMELL == ledger_constants.SEVERITY_SMELL


def test_should_classify_the_package_inventory_check_as_advisory() -> None:
    assert severity_for_check_id(CHECK_ID_PACKAGE_INVENTORY) == SEVERITY_SMELL


def test_should_pass_a_report_that_carries_advisory_findings_alone() -> None:
    report = RepositoryCheckReport((_inventory_finding(),), ())
    assert report.all_smell_findings == (_inventory_finding(),)
    assert report.all_breaking_findings == ()
    assert report.exit_code == SUCCESS_EXIT_CODE


def test_should_fail_a_report_that_carries_a_breaking_finding() -> None:
    breaking_finding = RepositoryFinding(
        CHECK_ID_CLAUDE_MD_ORPHANS, "notes/CLAUDE.md", "references missing file x.py"
    )
    report = RepositoryCheckReport((_inventory_finding(), breaking_finding), ())
    assert report.all_breaking_findings == (breaking_finding,)
    assert report.exit_code == FINDINGS_EXIT_CODE


def test_should_fail_closed_over_an_advisory_finding() -> None:
    report = RepositoryCheckReport(
        (_inventory_finding(),), (CHECK_ID_PACKAGE_INVENTORY,)
    )
    assert report.exit_code == FAILED_CHECK_EXIT_CODE


def _inventory_finding() -> RepositoryFinding:
    return RepositoryFinding(
        CHECK_ID_PACKAGE_INVENTORY,
        "pipeline/check_dialer_seam_cli.py",
        "production file is absent from package inventory",
    )
