#!/usr/bin/env python3
"""Shared deterministic checks for prompt workflow hooks."""

from __future__ import annotations

import re
import textwrap
from typing import Iterable

from prompt_workflow_gate_config import (
    AMBIGUOUS_SCOPE_TERMS,
    COMPILED_NEGATIVE_INDIRECT_PATTERNS,
    COMPILED_NEGATIVE_KEYWORD_PATTERNS,
    DEBUG_INTENT_MARKERS,
    INTERNAL_OBJECT_MARKERS,
    PROMPT_WORKFLOW_RESPONSE_MARKERS,
    REQUIRED_CHECKLIST_ROWS,
    REQUIRED_SCOPE_ANCHORS,
    REQUIRED_XML_SECTIONS,
)

TRIPLE_BACKTICK = "```"
AUDIT_LINE_PATTERN = re.compile(r"^\s*[●•]?\s*(Audit:\s*.+?)\s*$")

def _line_opens_xml_fence(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith(TRIPLE_BACKTICK):
        return False
    fence_marker_length = len(TRIPLE_BACKTICK)
    remainder = stripped[fence_marker_length:].strip()
    return remainder == "xml" or remainder.startswith("xml ")

def _line_is_bare_fence_close(line: str) -> bool:
    return line.strip() == TRIPLE_BACKTICK

def _line_opens_inner_markdown_fence(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith(TRIPLE_BACKTICK):
        return False
    return stripped != TRIPLE_BACKTICK

def _collect_inner_markdown_fence(
    lines: list[str],
    start_index: int,
) -> tuple[list[str], int]:
    inner_lines: list[str] = []
    index = start_index
    while index < len(lines):
        current_line = lines[index]
        inner_lines.append(current_line)
        index += 1
        if _line_is_bare_fence_close(current_line):
            break
    return inner_lines, index

def _collect_xml_fence_body(
    lines: list[str],
    start_index: int,
) -> tuple[list[str], int]:
    body_lines: list[str] = []
    index = start_index
    while index < len(lines):
        current_line = lines[index]
        if _line_is_bare_fence_close(current_line):
            return body_lines, index + 1
        if _line_opens_inner_markdown_fence(current_line):
            inner_lines, index = _collect_inner_markdown_fence(lines, index)
            body_lines.extend(inner_lines)
            continue
        body_lines.append(current_line)
        index += 1
    return body_lines, index

def extract_fenced_xml_content(text: str) -> str:
    """Extract bodies of ```xml fenced blocks.

    The closing delimiter is a line whose stripped text is exactly three backticks.
    Inner Markdown code fences (for example a line starting with three backticks
    plus a language tag) are scanned until their own closing backtick line so the
    outer ``xml`` fence does not end early.
    """
    results: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if not _line_opens_xml_fence(lines[index]):
            index += 1
            continue
        body_lines, index = _collect_xml_fence_body(lines, index + 1)
        results.append("\n".join(body_lines))
    return "\n".join(results)

def _line_is_audit_line(line: str) -> bool:
    return AUDIT_LINE_PATTERN.match(line) is not None

def _normalize_audit_line(line: str) -> str:
    match = AUDIT_LINE_PATTERN.match(line)
    if match:
        return match.group(1).strip()
    return line.strip()

def _line_starts_exported_artifact(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _line_opens_xml_fence(stripped):
        return True
    exported_artifact_pattern = re.compile(
        r"^<(\?xml\b|prompt\b|runtime_context\b|role\b|background\b|instructions\b|constraints\b|output_format\b|illustrations\b|open_question\b)",
    )
    return exported_artifact_pattern.match(stripped) is not None

def _trim_trailing_blank_lines(lines: list[str]) -> list[str]:
    trimmed = list(lines)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()
    return trimmed

def _trim_flattened_export_tail(lines: list[str]) -> list[str]:
    trimmed = _trim_trailing_blank_lines(lines)
    while trimmed and trimmed[-1].lstrip().startswith("✻ "):
        trimmed.pop()
        trimmed = _trim_trailing_blank_lines(trimmed)
    return trimmed

def _find_last_audit_index(lines: list[str]) -> int | None:
    last_audit_index: int | None = None
    for index, line in enumerate(lines):
        if _line_is_audit_line(line):
            last_audit_index = index
    return last_audit_index

def _find_first_artifact_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if _line_starts_exported_artifact(line):
            return index
    return None

def _rebuild_from_existing_fence(audit_line: str, artifact_text: str) -> str:
    fenced_body = extract_fenced_xml_content(artifact_text).strip()
    if not fenced_body:
        return audit_line
    return f"{audit_line}\n```xml\n{fenced_body}\n```"

def _rebuild_from_flattened_body(audit_line: str, artifact_text: str) -> str:
    dedented_body = textwrap.dedent(artifact_text).strip("\n")
    if not dedented_body:
        return audit_line
    return f"{audit_line}\n```xml\n{dedented_body}\n```"

def _rebuild_canonical_export(audit_line: str, artifact_lines: list[str]) -> str:
    if not artifact_lines:
        return audit_line
    artifact_text = "\n".join(artifact_lines).rstrip()
    if _line_opens_xml_fence(artifact_lines[0]):
        return _rebuild_from_existing_fence(audit_line, artifact_text)
    return _rebuild_from_flattened_body(audit_line, artifact_text)

def normalize_prompt_workflow_export(text: str) -> str:
    """Return the last successful Audit + fenced XML pair from a message or export.

    Saved transcript exports can flatten blocked retry turns and strip the outer
    ``xml`` fence. This helper keeps only the last successful ``Audit:`` attempt
    and rebuilds the canonical audit-plus-fence shape used by prompt-workflow
    hooks and reviewers.
    """
    lines = text.splitlines()
    last_audit_index = _find_last_audit_index(lines)
    if last_audit_index is None:
        return text.strip()
    audit_line = _normalize_audit_line(lines[last_audit_index])
    artifact_index = _find_first_artifact_index(lines[last_audit_index + 1 :])
    if artifact_index is None:
        return audit_line
    artifact_lines = _trim_flattened_export_tail(
        lines[last_audit_index + 1 + artifact_index :],
    )
    return _rebuild_canonical_export(audit_line, artifact_lines)

def extract_fenced_xml_content_from_export(text: str) -> str:
    """Extract fenced XML from a canonical message or flattened transcript export."""
    normalized = normalize_prompt_workflow_export(text)
    return extract_fenced_xml_content(normalized)

def missing_required_xml_sections(text: str) -> list[str]:
    fenced_body = extract_fenced_xml_content(text)
    if not fenced_body.strip():
        return []
    missing_sections: list[str] = []
    for section_name in REQUIRED_XML_SECTIONS:
        open_tag = re.compile(rf"<{re.escape(section_name)}(\s[^>]*)?>")
        close_tag = re.compile(rf"</{re.escape(section_name)}>")
        if not open_tag.search(fenced_body) or not close_tag.search(fenced_body):
            missing_sections.append(section_name)
    return missing_sections

def _build_negative_keyword_violation(
    match: re.Match[str],
    line_number: int,
    line_text: str,
) -> dict[str, str | int]:
    return {
        "keyword": match.group(),
        "line_number": line_number,
        "line_text": line_text.strip(),
    }

def _find_pattern_violations(
    patterns: Iterable[re.Pattern[str]],
    line_text: str,
    line_number: int,
) -> list[dict[str, str | int]]:
    violations: list[dict[str, str | int]] = []
    for pattern in patterns:
        match = pattern.search(line_text)
        if match:
            violations.append(
                _build_negative_keyword_violation(match, line_number, line_text),
            )
    return violations

def find_negative_keywords_in_fenced_xml(
    text: str,
) -> list[dict[str, str | int]]:
    fenced_content = extract_fenced_xml_content(text)
    if not fenced_content:
        return []
    all_violations: list[dict[str, str | int]] = []
    for line_index, each_line in enumerate(fenced_content.splitlines(), start=1):
        all_violations.extend(
            _find_pattern_violations(
                COMPILED_NEGATIVE_KEYWORD_PATTERNS,
                each_line,
                line_index,
            ),
        )
        all_violations.extend(
            _find_pattern_violations(
                COMPILED_NEGATIVE_INDIRECT_PATTERNS,
                each_line,
                line_index,
            ),
        )
    return all_violations

def _contains_any_marker(text: str, markers: Iterable[str]) -> bool:
    lower_text = text.lower()
    return any(marker.lower() in lower_text for marker in markers)

def has_debug_intent(text: str) -> bool:
    return _contains_any_marker(text, DEBUG_INTENT_MARKERS)

def has_internal_object_leak(text: str) -> bool:
    return _contains_any_marker(text, INTERNAL_OBJECT_MARKERS)

def missing_scope_anchors(text: str) -> list[str]:
    return [anchor for anchor in REQUIRED_SCOPE_ANCHORS if anchor not in text]

def find_ambiguous_scope_terms(text: str) -> list[str]:
    if "scope" not in text.lower():
        return []
    matches: list[str] = []
    lower_text = text.lower()
    for term in AMBIGUOUS_SCOPE_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lower_text):
            matches.append(term)
    return matches

def has_checklist_container(text: str) -> bool:
    lower_text = text.lower()
    return "checklist_results" in lower_text or "checklist:" in lower_text

def missing_checklist_rows(text: str) -> list[str]:
    return [row for row in REQUIRED_CHECKLIST_ROWS if row not in text]

def is_prompt_workflow_response(text: str) -> bool:
    lower_text = text.lower()
    matched_markers = [
        marker for marker in PROMPT_WORKFLOW_RESPONSE_MARKERS if marker in lower_text
    ]
    return len(matched_markers) >= 2

def missing_context_control_signals(text: str) -> list[str]:
    required_signals: tuple[str, ...] = (
        "base_minimal_instruction_layer: true",
        "on_demand_skill_loading: true",
    )
    lowered = text.lower()
    return [signal for signal in required_signals if signal not in lowered]
