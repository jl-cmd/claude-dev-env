"""Stable text reports for committed-tree repository checks."""

from __future__ import annotations

from repository_checks.config import constants as repository_constants
from repository_checks.models import RepositoryCheckReport


def render_report(report: RepositoryCheckReport) -> str:
    """Render findings and failed checks as newline-terminated text.

    Args:
        report: Findings and failed check identifiers.

    Returns:
        The report body, or an empty string when the tree is clean.
    """
    all_lines = [
        repository_constants.FINDING_LINE_TEMPLATE.format(
            check_id=each_finding.check_id,
            relative_path=each_finding.relative_path,
            message=each_finding.message,
        )
        for each_finding in report.all_findings
    ]
    all_lines.extend(_failed_check_lines(report))
    if not all_lines:
        return repository_constants.EMPTY_REPORT_TEXT
    return (
        repository_constants.REPORT_LINE_SEPARATOR.join(all_lines)
        + repository_constants.REPORT_LINE_SEPARATOR
    )


def _failed_check_lines(report: RepositoryCheckReport) -> list[str]:
    return [
        repository_constants.RULE_FAILED_LINE_TEMPLATE.format(check_id=each_check_id)
        for each_check_id in report.all_failed_check_ids
    ]
