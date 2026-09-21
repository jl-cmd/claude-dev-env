"""Record advisory committed-tree findings in the follow-up ledger."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

from repository_checks.config.constants import (
    ALL_FAIL_CLOSED_EXCEPTION_TYPES,
    FOLLOWUP_LEDGER_MODULE_NAME,
    SEVERITY_SMELL,
)
from repository_checks.hook_modules import load_hooks_module
from repository_checks.models import RepositoryCheckReport, RepositoryFinding


def record_smell_findings(repository_root: Path, report: RepositoryCheckReport) -> None:
    """Append every advisory finding to the repository's follow-up ledger.

    The ledger keeps the gate's decision unchanged, so a ledger that cannot be
    loaded or written leaves the report's exit code as it stands.

    Args:
        repository_root: The repository whose ledger receives the findings.
        report: The findings this run produced.
    """
    if not report.all_smell_findings:
        return
    try:
        ledger = load_hooks_module(FOLLOWUP_LEDGER_MODULE_NAME)
        origin_commit = ledger.head_commit(repository_root)
        for each_finding in report.all_smell_findings:
            _append_finding(ledger, repository_root, each_finding, origin_commit)
    except ALL_FAIL_CLOSED_EXCEPTION_TYPES:
        return


def _append_finding(
    ledger: ModuleType,
    repository_root: Path,
    finding: RepositoryFinding,
    origin_commit: str,
) -> None:
    ledger.record_followup_finding(
        repository_root,
        ledger.FollowupFinding(
            finding.check_id,
            finding.relative_path,
            finding.message,
            finding.check_id,
            SEVERITY_SMELL,
            origin_commit,
        ),
    )
