"""Unit tests for shared prompt workflow gate logic."""

from prompt_workflow_gate_core import (
    find_ambiguous_scope_terms,
    has_explicit_execution_intent,
    has_internal_object_leak,
    missing_checklist_rows,
    missing_scope_anchors,
)


def test_execution_intent_marker_detected() -> None:
    assert has_explicit_execution_intent("execution_intent: explicit")


def test_internal_object_leak_detected() -> None:
    text = '{"pipeline_mode": "internal_section_refinement_with_final_audit"}'
    assert has_internal_object_leak(text)


def test_missing_scope_anchors_returns_expected_rows() -> None:
    text = "Scope block includes target_local_roots only."
    missing = missing_scope_anchors(text)
    assert "target_canonical_roots" in missing
    assert "completion_boundary" in missing


def test_missing_checklist_rows_detected() -> None:
    text = "checklist_results: structured_scoped_instructions only"
    missing = missing_checklist_rows(text)
    assert "completion_boundary_measurable" in missing


def test_ambiguous_scope_terms_detected() -> None:
    text = "Scope applies to this session and current files."
    terms = find_ambiguous_scope_terms(text)
    assert "this session" in terms
    assert "current files" in terms
