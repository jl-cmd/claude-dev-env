"""Stable text reports for committed-tree repository checks."""

from __future__ import annotations

from repository_checks.config import constants as repository_constants
from repository_checks.models import RepositoryCheckReport, RepositoryFinding


def render_report(report: RepositoryCheckReport) -> str:
    """Render findings and failed checks as newline-terminated text.

    An advisory finding carries an ``advisory:`` prefix, so a reader of a
    passing run can tell the reported line from one that failed the tree.

    ::

        claude-md-orphans: notes/CLAUDE.md: references missing file x.py
        advisory: package-inventory: pipeline/seam.py: production file is
        absent from package inventory

    Args:
        report: Findings and failed check identifiers.

    Returns:
        The report body, or an empty string when the tree is clean.
    """
    all_lines = [
        _finding_line(each_finding) for each_finding in report.all_findings
    ]
    all_lines.extend(_failed_check_lines(report))
    if not all_lines:
        return repository_constants.EMPTY_REPORT_TEXT
    return (
        repository_constants.REPORT_LINE_SEPARATOR.join(all_lines)
        + repository_constants.REPORT_LINE_SEPARATOR
    )


def _finding_line(finding: RepositoryFinding) -> str:
    if finding.severity == repository_constants.SEVERITY_SMELL:
        line_template = repository_constants.ADVISORY_FINDING_LINE_TEMPLATE
    else:
        line_template = repository_constants.FINDING_LINE_TEMPLATE
    return line_template.format(
        check_id=finding.check_id,
        relative_path=finding.relative_path,
        message=finding.message,
    )


def _failed_check_lines(report: RepositoryCheckReport) -> list[str]:
    return [
        repository_constants.RULE_FAILED_LINE_TEMPLATE.format(check_id=each_check_id)
        for each_check_id in report.all_failed_check_ids
    ]
