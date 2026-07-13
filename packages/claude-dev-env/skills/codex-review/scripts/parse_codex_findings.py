"""Parse Codex reviewer text into stable internal finding records.

::

    all_findings = parse_codex_findings(reviewer_text)
    all_findings[0].title      # structured or freeform title
    all_findings[0].structured # True only for fenced JSON findings
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from codex_review_scripts_constants.findings_constants import (
    EMPTY_STRING,
    FENCED_JSON_BLOCK_PATTERN,
    FINDING_KEY_BODY,
    FINDING_KEY_FILE,
    FINDING_KEY_LINE_RANGE,
    FINDING_KEY_PRIORITY,
    FINDING_KEY_TITLE,
    FREEFORM_BULLET_PREFIX,
    FREEFORM_FINDING_LINE_PATTERN,
    NEWLINE,
)


@dataclass(frozen=True)
class CodexFinding:
    """One review finding in the skill's stable internal shape.

    ::

        CodexFinding(
            title="Restore empty-input handling",
            priority="P1",
            file="src/stats.py",
            line_range="2-2",
            body="Divides by zero on empty input.",
            structured=True,
        )

    Attributes:
        title: Short finding title.
        priority: Priority tag such as ``P1``.
        file: Path the finding points at.
        line_range: Inclusive line span as ``start-end``.
        body: Explanation text for the finding.
        structured: True when the finding came from fenced JSON.
    """

    title: str
    priority: str
    file: str
    line_range: str
    body: str
    structured: bool


def _string_field(all_finding_fields: dict[str, object], field_name: str) -> str:
    field_payload = all_finding_fields.get(field_name, EMPTY_STRING)
    if isinstance(field_payload, str):
        return field_payload
    return EMPTY_STRING


def _finding_from_structured_fields(
    all_finding_fields: dict[str, object],
) -> CodexFinding:
    return CodexFinding(
        title=_string_field(all_finding_fields, FINDING_KEY_TITLE),
        priority=_string_field(all_finding_fields, FINDING_KEY_PRIORITY),
        file=_string_field(all_finding_fields, FINDING_KEY_FILE),
        line_range=_string_field(all_finding_fields, FINDING_KEY_LINE_RANGE),
        body=_string_field(all_finding_fields, FINDING_KEY_BODY),
        structured=True,
    )


def _try_parse_structured_findings(reviewer_text: str) -> list[CodexFinding] | None:
    fenced_json_block = re.compile(
        FENCED_JSON_BLOCK_PATTERN,
        re.DOTALL | re.IGNORECASE,
    )
    for each_match in fenced_json_block.finditer(reviewer_text):
        block_body = each_match.group(1).strip()
        try:
            parsed_payload = json.loads(block_body)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed_payload, list):
            continue
        all_findings: list[CodexFinding] = []
        for each_entry in parsed_payload:
            if not isinstance(each_entry, dict):
                continue
            all_findings.append(_finding_from_structured_fields(each_entry))
        return all_findings
    return None


def _collect_freeform_body(
    all_lines: list[str],
    *,
    from_index: int,
) -> tuple[str, int]:
    all_body_lines: list[str] = []
    current_index = from_index
    while current_index < len(all_lines):
        current_line = all_lines[current_index]
        stripped_line = current_line.strip()
        if stripped_line.startswith(FREEFORM_BULLET_PREFIX):
            break
        if stripped_line:
            all_body_lines.append(stripped_line)
        current_index += 1
    return NEWLINE.join(all_body_lines), current_index


def _parse_freeform_findings(reviewer_text: str) -> list[CodexFinding]:
    freeform_finding_line = re.compile(FREEFORM_FINDING_LINE_PATTERN)
    all_lines = reviewer_text.splitlines()
    all_findings: list[CodexFinding] = []
    line_index = 0
    while line_index < len(all_lines):
        line_match = freeform_finding_line.match(all_lines[line_index].strip())
        if line_match is None:
            line_index += 1
            continue
        body_text, next_index = _collect_freeform_body(
            all_lines,
            from_index=line_index + 1,
        )
        all_findings.append(
            CodexFinding(
                title=line_match.group("title").strip(),
                priority=line_match.group("priority"),
                file=line_match.group("file_path").strip(),
                line_range=line_match.group("line_range"),
                body=body_text,
                structured=False,
            )
        )
        line_index = next_index
    return all_findings


def _floor_finding(reviewer_text: str) -> list[CodexFinding]:
    return [
        CodexFinding(
            title=EMPTY_STRING,
            priority=EMPTY_STRING,
            file=EMPTY_STRING,
            line_range=EMPTY_STRING,
            body=reviewer_text,
            structured=False,
        )
    ]


def parse_codex_findings(reviewer_text: str) -> list[CodexFinding]:
    """Parse reviewer text into findings; never drop non-empty text.

    ::

        parse_codex_findings("```json\\n[]\\n```")  # ok: []
        parse_codex_findings("loose note")          # ok: one unstructured finding

    Tries fenced JSON first (the custom-instructions contract), then the
    freeform ``- [P1] title — path:start-end`` shape, then a single floor
    finding that carries the raw text.

    Args:
        reviewer_text: Agent message text from a completed Codex review.

    Returns:
        Parsed findings; empty only when the text is blank or a structured
        empty array.
    """
    if not reviewer_text.strip():
        return []
    maybe_structured = _try_parse_structured_findings(reviewer_text)
    if maybe_structured is not None:
        return maybe_structured
    all_freeform_findings = _parse_freeform_findings(reviewer_text)
    if all_freeform_findings:
        return all_freeform_findings
    return _floor_finding(reviewer_text)
