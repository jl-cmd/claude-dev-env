"""Static lists and compiled regexes for prompt-workflow gate checks.

Edit this file to change scope anchors, checklist rows, markers, or keyword lists
without touching gate logic in prompt_workflow_gate_core.py.
"""

from __future__ import annotations

import re

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

REQUIRED_XML_SECTIONS: tuple[str, ...] = (
    "role",
    "background",
    "instructions",
    "constraints",
    "output_format",
)

COMPILED_NEGATIVE_KEYWORD_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
    for keyword in NEGATIVE_KEYWORDS_IN_ARTIFACT
)

COMPILED_NEGATIVE_INDIRECT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in NEGATIVE_INDIRECT_PATTERNS_IN_ARTIFACT
)
