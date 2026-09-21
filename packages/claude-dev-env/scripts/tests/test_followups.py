"""Behavior tests for recording advisory findings in the follow-up ledger."""

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
    CHECK_ID_CLAUDE_MD_ORPHANS,
    CHECK_ID_PACKAGE_INVENTORY,
    FOLLOWUP_LEDGER_MODULE_NAME,
    SEVERITY_SMELL,
)
from repository_checks.followups import record_smell_findings
from repository_checks.hook_modules import load_hooks_module
from repository_checks.models import RepositoryCheckReport, RepositoryFinding
from repository_policy_test_support import initialize_repository

_INVENTORY_PATH = "pipeline/check_dialer_seam_cli.py"
_INVENTORY_MESSAGE = "production file is absent from package inventory"


def test_should_record_an_advisory_finding_with_its_message(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    record_smell_findings(
        repository_root,
        RepositoryCheckReport(
            (
                RepositoryFinding(
                    CHECK_ID_PACKAGE_INVENTORY, _INVENTORY_PATH, _INVENTORY_MESSAGE
                ),
            ),
            (),
        ),
    )
    assert _recorded_rows(repository_root) == [
        (CHECK_ID_PACKAGE_INVENTORY, _INVENTORY_PATH, _INVENTORY_MESSAGE, SEVERITY_SMELL)
    ]


def test_should_record_one_row_for_a_finding_seen_twice(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    report = RepositoryCheckReport(
        (
            RepositoryFinding(
                CHECK_ID_PACKAGE_INVENTORY, _INVENTORY_PATH, _INVENTORY_MESSAGE
            ),
        ),
        (),
    )
    record_smell_findings(repository_root, report)
    record_smell_findings(repository_root, report)
    assert len(_recorded_rows(repository_root)) == 1


def test_should_leave_a_breaking_finding_out_of_the_ledger(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    record_smell_findings(
        repository_root,
        RepositoryCheckReport(
            (
                RepositoryFinding(
                    CHECK_ID_CLAUDE_MD_ORPHANS,
                    "notes/CLAUDE.md",
                    "references missing file absent_helper.py",
                ),
            ),
            (),
        ),
    )
    assert _recorded_rows(repository_root) == []


def _recorded_rows(repository_root: Path) -> list[tuple[str, str, str, str]]:
    ledger = load_hooks_module(FOLLOWUP_LEDGER_MODULE_NAME)
    return [
        (
            each_finding.check_id,
            each_finding.file_path,
            each_finding.message,
            each_finding.severity,
        )
        for each_finding in ledger.all_recorded_findings(repository_root)
    ]
