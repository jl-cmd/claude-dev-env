"""Shared report types for committed-tree repository checks."""

from __future__ import annotations

from dataclasses import dataclass

from repository_checks.config.constants import (
    FAILED_CHECK_EXIT_CODE,
    FINDINGS_EXIT_CODE,
    SEVERITY_BREAKING,
    SEVERITY_BY_CHECK_ID,
    SEVERITY_SMELL,
    SUCCESS_EXIT_CODE,
)


def severity_for_check_id(check_id: str) -> str:
    """Return the severity a check identifier declares.

    A check identifier absent from the table reads as breaking, so a check
    added without a severity row fails the tree rather than passing quietly.

    Args:
        check_id: Stable identifier of the check that raised a finding.

    Returns:
        Either SEVERITY_BREAKING or SEVERITY_SMELL.
    """
    return SEVERITY_BY_CHECK_ID.get(check_id, SEVERITY_BREAKING)


@dataclass(frozen=True)
class RepositoryFinding:
    """One committed-tree finding with a stable check id and relative path."""

    check_id: str
    relative_path: str
    message: str

    @property
    def severity(self) -> str:
        """Return the severity this finding's check identifier declares."""
        return severity_for_check_id(self.check_id)


@dataclass(frozen=True)
class RepositoryCheckReport:
    """Sorted findings and the check ids that failed while they ran.

    Splits its findings into the breaking ones and the advisory ones, and
    derives the exit code from the breaking ones alone.
    """

    all_findings: tuple[RepositoryFinding, ...]
    all_failed_check_ids: tuple[str, ...]

    @property
    def all_breaking_findings(self) -> tuple[RepositoryFinding, ...]:
        """Return the findings that fail the tree."""
        return self._findings_of_severity(SEVERITY_BREAKING)

    @property
    def all_smell_findings(self) -> tuple[RepositoryFinding, ...]:
        """Return the findings that report and leave the tree passing."""
        return self._findings_of_severity(SEVERITY_SMELL)

    @property
    def exit_code(self) -> int:
        """Return the process status for this report."""
        if self.all_failed_check_ids:
            return FAILED_CHECK_EXIT_CODE
        if self.all_breaking_findings:
            return FINDINGS_EXIT_CODE
        return SUCCESS_EXIT_CODE

    def _findings_of_severity(self, severity: str) -> tuple[RepositoryFinding, ...]:
        return tuple(
            each_finding
            for each_finding in self.all_findings
            if each_finding.severity == severity
        )
