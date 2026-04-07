"""Unit tests for shared prompt workflow gate logic."""

from prompt_workflow_gate_core import (
    find_ambiguous_scope_terms,
    has_checklist_container,
    has_explicit_execution_intent,
    has_structured_execution_intent,
    has_internal_object_leak,
    is_prompt_workflow_response,
    missing_checklist_rows,
    missing_scope_anchors,
)


def test_execution_intent_marker_detected() -> None:
    assert has_explicit_execution_intent("execution_intent: explicit")


def test_structured_execution_intent_detected_from_contract_field() -> None:
    assert has_structured_execution_intent({"execution_intent": "explicit"})


def test_structured_execution_intent_detected_from_boolean_flag() -> None:
    assert has_structured_execution_intent({"execution_intent_explicit": True})


def test_internal_object_leak_detected() -> None:
    text = '{"pipeline_mode": "internal_section_refinement_with_final_audit"}'
    assert has_internal_object_leak(text)


def test_missing_scope_anchors_returns_expected_rows() -> None:
    text = "target_local_roots only."
    missing = missing_scope_anchors(text)
    assert "target_canonical_roots" in missing
    assert "completion_boundary" in missing


def test_missing_checklist_rows_detected() -> None:
    text = "checklist_results: structured_scoped_instructions only"
    missing = missing_checklist_rows(text)
    assert "completion_boundary_measurable" in missing


def test_checklist_container_detection() -> None:
    assert has_checklist_container("checklist_results:\n- structured_scoped_instructions")


def test_prompt_workflow_response_detection() -> None:
    message = (
        "overall_status: pass\n"
        "target_local_roots: /repo\n"
        "comparison_basis: current behavior vs deterministic guarantees\n"
    )
    assert is_prompt_workflow_response(message)


def test_ambiguous_scope_terms_detected() -> None:
    text = "Scope applies to this session and current files."
    terms = find_ambiguous_scope_terms(text)
    assert "this session" in terms
    assert "current files" in terms
