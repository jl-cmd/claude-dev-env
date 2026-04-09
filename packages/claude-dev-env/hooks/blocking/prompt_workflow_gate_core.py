#!/usr/bin/env python3
"""Shared deterministic checks for prompt workflow hooks."""

from __future__ import annotations

import re
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


def _line_opens_xml_fence(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("```"):
        return False
    remainder = stripped[3:].strip()
    return remainder == "xml" or remainder.startswith("xml ")


def _line_is_bare_fence_close(line: str) -> bool:
    return line.strip() == "```"


def _line_opens_inner_markdown_fence(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("```"):
        return False
    return stripped != "```"


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
        if _line_opens_xml_fence(lines[index]):
            index += 1
            body_lines: list[str] = []
            while index < len(lines):
                line = lines[index]
                if _line_is_bare_fence_close(line):
                    index += 1
                    break
                if _line_opens_inner_markdown_fence(line):
                    body_lines.append(line)
                    index += 1
                    while index < len(lines):
                        inner_line = lines[index]
                        body_lines.append(inner_line)
                        index += 1
                        if _line_is_bare_fence_close(inner_line):
                            break
                    continue
                body_lines.append(line)
                index += 1
            results.append("\n".join(body_lines))
            continue
        index += 1
    return "\n".join(results)


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


def find_negative_keywords_in_fenced_xml(
    text: str,
) -> list[dict[str, str | int]]:
    fenced_content = extract_fenced_xml_content(text)
    if not fenced_content:
        return []
    fenced_lines = fenced_content.splitlines()
    all_violations: list[dict[str, str | int]] = []
    for line_index, each_line in enumerate(fenced_lines):
        for each_pattern in COMPILED_NEGATIVE_KEYWORD_PATTERNS:
            each_match = each_pattern.search(each_line)
            if each_match:
                all_violations.append({
                    "keyword": each_match.group(),
                    "line_number": line_index + 1,
                    "line_text": each_line.strip(),
                })
        for each_pattern in COMPILED_NEGATIVE_INDIRECT_PATTERNS:
            each_match = each_pattern.search(each_line)
            if each_match:
                all_violations.append({
                    "keyword": each_match.group(),
                    "line_number": line_index + 1,
                    "line_text": each_line.strip(),
                })
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
