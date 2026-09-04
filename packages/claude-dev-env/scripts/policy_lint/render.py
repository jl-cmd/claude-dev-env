from __future__ import annotations

import json
from collections.abc import Iterable
from enum import StrEnum

from .model import Diagnostic, EditorDiagnostic, LintReport


class ReportFormat(StrEnum):
    TEXT = "text"
    JSON = "json"
    EDITOR = "editor"


def render(report: LintReport, report_format: ReportFormat) -> str:
    """Render a lint report.

    ::

        json   -> {"diagnostics": [...], "schema_version": 1, ...}
        editor -> src/app.py:4:2: error: located finding [rule-a]
        text   -> editor lines plus diagnostics with no location

    Args:
        report: Lint report from the engine.
        report_format: text, json, or editor.

    Returns:
        The formatted report body.
    """
    if report_format is ReportFormat.JSON:
        return _render_json(report)
    if report_format is ReportFormat.EDITOR:
        return _render_editor(report)
    return _render_text(report)


def _render_json(report: LintReport) -> str:
    line_separator = "\n"
    return json.dumps(report.as_dict(), sort_keys=True) + line_separator


def _render_editor(report: LintReport) -> str:
    all_lines = [
        _editor_line(each_diagnostic)
        for each_diagnostic in report.editor_diagnostics()
    ]
    all_lines.extend(
        f"cde-lint:1:1: error: rule failed: {each_rule_id}"
        for each_rule_id in report.failed_rules
    )
    return _join_lines(all_lines)


def _render_text(report: LintReport) -> str:
    all_lines = [
        _text_line(each_diagnostic) for each_diagnostic in report.diagnostics
    ]
    all_lines.extend(
        f"error: rule failed: {each_rule_id}" for each_rule_id in report.failed_rules
    )
    return _join_lines(all_lines)


def _join_lines(all_lines: Iterable[str]) -> str:
    line_separator = "\n"
    all_collected_lines = list(all_lines)
    if not all_collected_lines:
        return ""
    return line_separator.join(all_collected_lines) + line_separator


def _editor_line(diagnostic: EditorDiagnostic) -> str:
    return (
        f"{diagnostic.path.as_posix()}:{diagnostic.line}:{diagnostic.column}: "
        f"{diagnostic.severity.value}: {diagnostic.message} [{diagnostic.rule_id}]"
    )


def _text_line(diagnostic: Diagnostic) -> str:
    if diagnostic.location is None:
        return (
            f"{diagnostic.severity.value}: {diagnostic.message} [{diagnostic.rule_id}]"
        )
    normalized_location = diagnostic.location.normalized()
    return (
        f"{normalized_location.path.as_posix()}:{normalized_location.start_line}:"
        f"{normalized_location.start_column}: {diagnostic.severity.value}: "
        f"{diagnostic.message} [{diagnostic.rule_id}]"
    )
