"""Tests for prompt_workflow_validate module (shared validator + CLI entry point)."""

import subprocess
import sys
from pathlib import Path

import pytest

from prompt_workflow_validate import ValidationResult, validate_prompt_workflow

VALIDATOR_MODULE_PATH = Path(__file__).parent / "prompt_workflow_validate.py"


def _full_checklist_rows() -> str:
    return (
        "checklist_results:\n"
        "- structured_scoped_instructions\n"
        "- sequential_steps_present\n"
        "- positive_framing\n"
        "- acceptance_criteria_defined\n"
        "- safety_reversibility_language\n"
        "- reversible_action_and_safety_check_guidance\n"
        "- concrete_output_contract\n"
        "- scope_boundary_present\n"
        "- explicit_scope_anchors_present\n"
        "- all_instructions_artifact_bound\n"
        "- scope_terms_explicit_and_anchored\n"
        "- completion_boundary_measurable\n"
        "- citation_grounding_policy_present\n"
        "- source_priority_rules_present\n"
        "- artifact_language_confidence\n"
    )


def _wrap_five_section_scaffold(inner_body: str) -> str:
    has_instructions = "<instructions>" in inner_body
    has_constraints = "<constraints>" in inner_body
    instructions_section = (
        "" if has_instructions else "<instructions>Test instructions sentence one.</instructions>\n"
    )
    constraints_section = (
        "" if has_constraints else "<constraints>Test constraints sentence one.</constraints>\n"
    )
    return (
        "<role>Test role sentence one.</role>\n"
        "<background>Test background sentence one.</background>\n"
        f"{instructions_section}"
        f"{inner_body}\n"
        f"{constraints_section}"
        "<output_format>Test output format sentence one.</output_format>\n"
    )


def _build_prompt_workflow_message_with_fenced_xml(fenced_xml_body: str) -> str:
    return (
        "Audit: pass 15/15\n"
        "```xml\n" + fenced_xml_body + "\n```\n"
        "overall_status: pass\n" + _full_checklist_rows() + "target_local_roots\n"
        "target_canonical_roots\n"
        "target_file_globs\n"
        "comparison_basis\n"
        "completion_boundary\n"
        "base_minimal_instruction_layer: true\n"
        "on_demand_skill_loading: true\n"
    )


class TestValidatePromptWorkflowFunction:
    """Tests that exercise the shared validate_prompt_workflow function directly."""

    def test_allowed_complete_message_with_fenced_xml(self) -> None:
        fenced_content = _wrap_five_section_scaffold(
            "<instructions>Ensure all functions have explicit return types.</instructions>"
        )
        message = _build_prompt_workflow_message_with_fenced_xml(fenced_content)
        validation_result = validate_prompt_workflow(message)
        assert validation_result.allowed is True
        assert validation_result.reasons == ()

    def test_blocked_missing_context_control_lines(self) -> None:
        message = (
            "overall_status: pass\n"
            + _full_checklist_rows()
            + "target_local_roots\n"
            + "target_canonical_roots\n"
            + "target_file_globs\n"
            + "comparison_basis\n"
            + "completion_boundary\n"
        )
        validation_result = validate_prompt_workflow(message)
        assert validation_result.allowed is False
        assert "missing_context_signals" in validation_result.reason_codes
        assert any(
            "context-control" in each_message
            for each_message in validation_result.reason_messages
        )

    def test_allowed_empty_message(self) -> None:
        validation_result = validate_prompt_workflow("")
        assert validation_result.allowed is True

    def test_allowed_non_workflow_message(self) -> None:
        validation_result = validate_prompt_workflow("Just a regular response.")
        assert validation_result.allowed is True

    def test_blocked_internal_object_leak(self) -> None:
        leak_message = (
            '{"pipeline_mode": "internal_section_refinement_with_final_audit"}'
        )
        validation_result = validate_prompt_workflow(leak_message)
        assert validation_result.allowed is False
        assert "internal_object_leak" in validation_result.reason_codes

    def test_allowed_internal_object_with_debug_context(self) -> None:
        leak_message = (
            '{"pipeline_mode": "internal_section_refinement_with_final_audit"}'
        )
        validation_result = validate_prompt_workflow(
            leak_message,
            user_context="debug: show internal pipeline object",
        )
        assert validation_result.allowed is True

    def test_blocked_missing_checklist_rows(self) -> None:
        message = (
            "overall_status: pass\n"
            "checklist_results: structured_scoped_instructions\n"
            "target_local_roots\n"
            "target_canonical_roots\n"
            "target_file_globs\n"
            "comparison_basis\n"
            "completion_boundary\n"
        )
        validation_result = validate_prompt_workflow(message)
        assert validation_result.allowed is False
        assert "missing_checklist_rows" in validation_result.reason_codes

    def test_blocked_negative_keywords_in_fenced_xml(self) -> None:
        fenced_content = _wrap_five_section_scaffold(
            "<instructions>Do not leave return types implicit.</instructions>"
        )
        message = _build_prompt_workflow_message_with_fenced_xml(fenced_content)
        validation_result = validate_prompt_workflow(message)
        assert validation_result.allowed is False
        assert "negative_keywords_in_artifact" in validation_result.reason_codes

    def test_blocked_ambiguous_scope(self) -> None:
        message = (
            "overall_status: pass\n"
            + _full_checklist_rows()
            + "scope block includes target_local_roots target_canonical_roots "
            + "target_file_globs comparison_basis completion_boundary "
            + "base_minimal_instruction_layer: true\n"
            + "on_demand_skill_loading: true\n"
            + "and applies to this session."
        )
        validation_result = validate_prompt_workflow(message)
        assert validation_result.allowed is False
        assert "ambiguous_scope" in validation_result.reason_codes

    def test_reason_messages_property(self) -> None:
        message = (
            "overall_status: pass\n"
            + _full_checklist_rows()
            + "target_local_roots\n"
            + "target_canonical_roots\n"
            + "target_file_globs\n"
            + "comparison_basis\n"
            + "completion_boundary\n"
        )
        validation_result = validate_prompt_workflow(message)
        assert len(validation_result.reason_messages) == 1
        assert len(validation_result.reason_codes) == 1

    def test_blocked_missing_scope_anchors(self) -> None:
        message = (
            "overall_status: pass\n"
            + _full_checklist_rows()
            + "base_minimal_instruction_layer: true\n"
            + "on_demand_skill_loading: true\n"
        )
        validation_result = validate_prompt_workflow(message)
        assert validation_result.allowed is False
        assert "missing_scope_anchors" in validation_result.reason_codes

    def test_blocked_missing_xml_sections_in_fenced_artifact(self) -> None:
        fenced_body = (
            "<role>Test role sentence one.</role>\n"
            "<instructions>Test instructions sentence one.</instructions>\n"
            "<constraints>Test constraints sentence one.</constraints>\n"
            "<output_format>Test output format sentence one.</output_format>\n"
        )
        message = _build_prompt_workflow_message_with_fenced_xml(fenced_body)
        validation_result = validate_prompt_workflow(message)
        assert validation_result.allowed is False
        assert "missing_xml_sections" in validation_result.reason_codes
        assert any(
            "background" in each_message
            for each_message in validation_result.reason_messages
        )

    def test_allows_positive_phrasing_inside_fenced_xml(self) -> None:
        fenced_content = _wrap_five_section_scaffold(
            "<instructions>Ensure all functions have explicit return types.</instructions>"
        )
        message = _build_prompt_workflow_message_with_fenced_xml(fenced_content)
        validation_result = validate_prompt_workflow(message)
        assert validation_result.allowed is True

    def test_permits_negative_keywords_outside_fenced_xml(self) -> None:
        fenced_inner = _wrap_five_section_scaffold(
            "<instructions>Ensure all functions have explicit return types.</instructions>"
        )
        message = (
            "Audit: pass 15/15\n"
            "Do not skip the audit line.\n"
            "```xml\n" + fenced_inner + "\n```\n"
            "overall_status: pass\n" + _full_checklist_rows() + "target_local_roots\n"
            "target_canonical_roots\n"
            "target_file_globs\n"
            "comparison_basis\n"
            "completion_boundary\n"
            "base_minimal_instruction_layer: true\n"
            "on_demand_skill_loading: true\n"
        )
        validation_result = validate_prompt_workflow(message)
        assert validation_result.allowed is True


@pytest.mark.parametrize(
    ("banned_pattern_name", "fenced_xml_content"),
    [
        ("do_not", "<instructions>Do not leave return types implicit.</instructions>"),
        ("avoid", "<instructions>Avoid missing return types.</instructions>"),
        ("never", "<constraints>Never store credentials in plain text.</constraints>"),
        ("without", "<instructions>Deploy without running tests first.</instructions>"),
        ("prevent", "<constraints>Prevent unauthorized access to the API.</constraints>"),
        ("reject", "<constraints>Reject all unsigned commits.</constraints>"),
        ("cannot", "<constraints>The API cannot accept unauthenticated requests.</constraints>"),
        ("unless", "<constraints>Skip the build step unless the user explicitly approves.</constraints>"),
        ("must_not", "<constraints>The script must not produce duplicates.</constraints>"),
        ("must_never", "<constraints>You must never store credentials in environment variables.</constraints>"),
        ("instead_of", "<instructions>Use explicit types instead of implicit ones.</instructions>"),
        ("rather_than", "<constraints>Prefer explicit types rather than inferred ones.</constraints>"),
        ("as_opposed_to", "<instructions>Use Grid as opposed to floats for layout.</instructions>"),
    ],
)
def test_blocks_banned_pattern_inside_fenced_xml(
    banned_pattern_name: str,
    fenced_xml_content: str,
) -> None:
    message = _build_prompt_workflow_message_with_fenced_xml(
        _wrap_five_section_scaffold(fenced_xml_content)
    )
    validation_result = validate_prompt_workflow(message)
    assert validation_result.allowed is False
    assert "negative_keywords_in_artifact" in validation_result.reason_codes


class TestValidatorCli:
    """Tests that exercise the CLI entry point via subprocess."""

    def test_cli_exits_zero_for_valid_content(self, tmp_path: Path) -> None:
        fenced_content = _wrap_five_section_scaffold(
            "<instructions>Ensure all functions have explicit return types.</instructions>"
        )
        draft_file = tmp_path / "draft.xml"
        draft_file.write_text(
            _build_prompt_workflow_message_with_fenced_xml(fenced_content),
            encoding="utf-8",
        )
        completed_process = subprocess.run(
            [sys.executable, str(VALIDATOR_MODULE_PATH), str(draft_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed_process.returncode == 0
        assert completed_process.stderr.strip() == ""

    def test_cli_exits_two_with_bracketed_reason_code_on_stderr(
        self,
        tmp_path: Path,
    ) -> None:
        message = (
            "overall_status: pass\n"
            + _full_checklist_rows()
            + "target_local_roots\n"
            + "target_canonical_roots\n"
            + "target_file_globs\n"
            + "comparison_basis\n"
            + "completion_boundary\n"
        )
        draft_file = tmp_path / "draft.xml"
        draft_file.write_text(message, encoding="utf-8")
        completed_process = subprocess.run(
            [sys.executable, str(VALIDATOR_MODULE_PATH), str(draft_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed_process.returncode == 2
        assert "[missing_context_signals]" in completed_process.stderr

    def test_cli_stderr_format_uses_reason_code_prefix(
        self,
        tmp_path: Path,
    ) -> None:
        fenced_content = _wrap_five_section_scaffold(
            "<instructions>Do not leave return types implicit.</instructions>"
        )
        draft_file = tmp_path / "draft.xml"
        draft_file.write_text(
            _build_prompt_workflow_message_with_fenced_xml(fenced_content),
            encoding="utf-8",
        )
        completed_process = subprocess.run(
            [sys.executable, str(VALIDATOR_MODULE_PATH), str(draft_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed_process.returncode == 2
        assert "[negative_keywords_in_artifact]" in completed_process.stderr
        assert "Banned negative keywords" in completed_process.stderr

    def test_cli_reads_from_stdin_when_no_file_argument(self) -> None:
        fenced_content = _wrap_five_section_scaffold(
            "<instructions>Ensure all functions have explicit return types.</instructions>"
        )
        valid_message = _build_prompt_workflow_message_with_fenced_xml(fenced_content)
        completed_process = subprocess.run(
            [sys.executable, str(VALIDATOR_MODULE_PATH)],
            input=valid_message,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed_process.returncode == 0
