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
    "no_destructive_shortcuts_guidance",
    "concrete_output_contract",
    "scope_boundary_present",
    "explicit_scope_anchors_present",
    "all_instructions_artifact_bound",
    "no_ambiguous_scope_terms",
    "completion_boundary_measurable",
    "citation_grounding_policy_present",
    "source_priority_rules_present",
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

DEBUG_INTENT_MARKERS: tuple[str, ...] = (
    "debug",
    "show internal",
    "raw internal object",
    "pipeline object",
)


def _contains_any_marker(text: str, markers: Iterable[str]) -> bool:
    lower_text = text.lower()
    return any(marker.lower() in lower_text for marker in markers)


def has_explicit_execution_intent(text: str) -> bool:
    return _contains_any_marker(text, EXPLICIT_EXECUTION_MARKERS)


def has_debug_intent(text: str) -> bool:
    return _contains_any_marker(text, DEBUG_INTENT_MARKERS)


def has_internal_object_leak(text: str) -> bool:
    return _contains_any_marker(text, INTERNAL_OBJECT_MARKERS)


def missing_scope_anchors(text: str) -> list[str]:
    if "scope block" not in text.lower() and "scope_block" not in text.lower():
        return []
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


def missing_checklist_rows(text: str) -> list[str]:
    if "checklist" not in text.lower() and "checklist_results" not in text.lower():
        return []
    return [row for row in REQUIRED_CHECKLIST_ROWS if row not in text]
