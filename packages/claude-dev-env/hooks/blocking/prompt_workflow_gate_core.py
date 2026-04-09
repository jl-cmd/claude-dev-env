#!/usr/bin/env python3
"""Shared deterministic checks for prompt workflow hooks."""

from __future__ import annotations

import re
from typing import Iterable

REQUIRED_SCOPE_ANCHORS: tuple[str, ...] = (
    "target_local_roots",
    "target_canonical_roots",
    "target_file_globs",
    "comparison_basis",
    "completion_boundary",
)

REQUIRED_CHECKLIST_ROWS: tuple[str, ...] = (
    "structured_scoped_instructions",
    "sequential_steps_present",
    "positive_framing",
    "acceptance_criteria_defined",
    "safety_reversibility_language",
    "reversible_action_and_safety_check_guidance",
    "concrete_output_contract",
    "scope_boundary_present",
    "explicit_scope_anchors_present",
    "all_instructions_artifact_bound",
    "scope_terms_explicit_and_anchored",
    "completion_boundary_measurable",
    "citation_grounding_policy_present",
    "source_priority_rules_present",
    "artifact_language_confidence",
)

REQUIRED_CONTEXT_CONTROL_SIGNALS: tuple[str, ...] = (
    "base_minimal_instruction_layer: true",
    "on_demand_skill_loading: true",
)

AMBIGUOUS_SCOPE_TERMS: tuple[str, ...] = (
    "this session",
    "current files",
    "here",
    "above",
    "as needed",
)

INTERNAL_OBJECT_MARKERS: tuple[str, ...] = (
    '"pipeline_mode": "internal_section_refinement_with_final_audit"',
    '"scope_block": {',
    '"required_sections": [',
    '"section_output_contract": {',
    '"merge_output_contract": {',
    '"audit_output_contract": {',
)

EXPLICIT_EXECUTION_MARKERS: tuple[str, ...] = (
    "/agent-prompt",
    "execution_intent: explicit",
    "execution_intent_explicit: true",
    "explicit execution intent",
    "explicit delegation intent",
)

PROMPT_WORKFLOW_RESPONSE_MARKERS: tuple[str, ...] = (
    "checklist_results",
    "overall_status",
    "scope anchors",
    "target_local_roots",
    "target_canonical_roots",
    "target_file_globs",
    "comparison_basis",
    "completion_boundary",
)

DEBUG_INTENT_MARKERS: tuple[str, ...] = (
    "debug",
    "show internal",
    "raw internal object",
    "pipeline object",
)


NEGATIVE_KEYWORDS_IN_ARTIFACT: tuple[str, ...] = (
    "no",
    "not",
    "don't",
    "do not",
    "never",
    "avoid",
    "without",
    "refrain",
    "stop",
    "prevent",
    "exclude",
    "prohibit",
    "forbid",
    "reject",
    "cannot",
    "unless",
)

NEGATIVE_INDIRECT_PATTERNS_IN_ARTIFACT: tuple[str, ...] = (
    r"instead of\s+\w+",
    r"rather than\s+\w+",
    r"as opposed to\s+\w+",
)

COMPILED_NEGATIVE_KEYWORD_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
    for keyword in NEGATIVE_KEYWORDS_IN_ARTIFACT
)

COMPILED_NEGATIVE_INDIRECT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in NEGATIVE_INDIRECT_PATTERNS_IN_ARTIFACT
)

FENCED_XML_BLOCK_PATTERN: re.Pattern[str] = re.compile(
    r"```xml\s*\n(.*?)```", re.DOTALL
)


def extract_fenced_xml_content(text: str) -> str:
    all_matches = FENCED_XML_BLOCK_PATTERN.findall(text)
    return "\n".join(all_matches)


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


def has_explicit_execution_intent(text: str) -> bool:
    return _contains_any_marker(text, EXPLICIT_EXECUTION_MARKERS)


def has_structured_execution_intent(tool_input: object) -> bool:
    if not isinstance(tool_input, dict):
        return False

    explicit_flag = tool_input.get("execution_intent_explicit")
    if isinstance(explicit_flag, bool):
        return explicit_flag

    intent_value = tool_input.get("execution_intent")
    if isinstance(intent_value, str):
        normalized = intent_value.strip().lower()
        return normalized in {"explicit", "execute", "delegation", "delegate"}
    if isinstance(intent_value, bool):
        return intent_value

    metadata = tool_input.get("metadata")
    if isinstance(metadata, dict):
        metadata_intent = metadata.get("execution_intent")
        if isinstance(metadata_intent, str):
            return metadata_intent.strip().lower() in {"explicit", "execute", "delegate"}
        if isinstance(metadata_intent, bool):
            return metadata_intent

    return False


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
    return [
        signal for signal in REQUIRED_CONTEXT_CONTROL_SIGNALS if signal not in text.lower()
    ]
