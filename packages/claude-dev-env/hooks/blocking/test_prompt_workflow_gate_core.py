"""Unit tests for shared prompt workflow gate logic."""

from prompt_workflow_gate_core import (
    extract_fenced_xml_content,
    find_ambiguous_scope_terms,
    has_checklist_container,
    has_internal_object_leak,
    is_prompt_workflow_response,
    missing_context_control_signals,
    missing_checklist_rows,
    missing_required_xml_sections,
    missing_scope_anchors,
)


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


def test_missing_context_control_signals_detected() -> None:
    missing = missing_context_control_signals("base_minimal_instruction_layer: true")
    assert "on_demand_skill_loading: true" in missing


def test_ambiguous_scope_terms_detected() -> None:
    text = "Scope applies to this session and current files."
    terms = find_ambiguous_scope_terms(text)
    assert "this session" in terms
    assert "current files" in terms


def _fenced_xml(body: str) -> str:
    return f"```xml\n{body}\n```"


def test_missing_required_xml_sections_all_present_returns_empty() -> None:
    body = (
        "<role>R.</role>\n"
        "<background>C.</background>\n"
        "<instructions>I.</instructions>\n"
        "<constraints>Co.</constraints>\n"
        "<output_format>O.</output_format>\n"
    )
    assert missing_required_xml_sections(_fenced_xml(body)) == []


def test_missing_required_xml_sections_missing_background() -> None:
    body = (
        "<role>R.</role>\n"
        "<instructions>I.</instructions>\n"
        "<constraints>Co.</constraints>\n"
        "<output_format>O.</output_format>\n"
    )
    assert missing_required_xml_sections(_fenced_xml(body)) == ["background"]


def test_missing_required_xml_sections_missing_role_and_output_format() -> None:
    body = (
        "<background>C.</background>\n"
        "<instructions>I.</instructions>\n"
        "<constraints>Co.</constraints>\n"
    )
    missing = missing_required_xml_sections(_fenced_xml(body))
    assert missing == ["role", "output_format"]


def test_missing_required_xml_sections_no_fence_returns_empty() -> None:
    assert missing_required_xml_sections("no fenced xml here") == []


def test_missing_required_xml_sections_prose_without_tags_counts_as_missing() -> None:
    body = (
        "<role>R.</role>\n"
        "background appears in prose but has no tags.\n"
        "<instructions>I.</instructions>\n"
        "<constraints>Co.</constraints>\n"
        "<output_format>O.</output_format>\n"
    )
    assert missing_required_xml_sections(_fenced_xml(body)) == ["background"]


def test_extract_fenced_xml_preserves_content_after_nested_inner_fence() -> None:
    message = (
        "```xml\n"
        "<role>R</role>\n"
        "<illustrations>\n"
        "```bash\necho hi\n```\n"
        "</illustrations>\n"
        "<background>B</background>\n"
        "<instructions>I</instructions>\n"
        "<constraints>C</constraints>\n"
        "<output_format>O</output_format>\n"
        "```\n"
    )
    extracted = extract_fenced_xml_content(message)
    assert "</illustrations>" in extracted
    assert "<background>B</background>" in extracted
