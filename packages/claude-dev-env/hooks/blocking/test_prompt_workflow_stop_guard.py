"""Tests for prompt-workflow-stop-guard hook."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parent / "prompt-workflow-stop-guard.py"

def _run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

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

def test_blocks_internal_object_leak_without_debug_intent() -> None:
    payload = {
        "last_assistant_message": '{"pipeline_mode": "internal_section_refinement_with_final_audit"}',
        "last_user_message": "just return the final prompt",
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["decision"] == "block"
    assert "Raw internal refinement object leakage" in response["reason"]

def test_allows_internal_object_with_debug_intent() -> None:
    payload = {
        "last_assistant_message": '{"pipeline_mode": "internal_section_refinement_with_final_audit"}',
        "last_user_message": "debug: show internal pipeline object",
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""

def test_blocks_missing_checklist_rows() -> None:
    payload = {
        "last_assistant_message": "overall_status: pass\nchecklist_results: structured_scoped_instructions",
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["decision"] == "block"
    assert "Deterministic checklist rows missing" in response["reason"]

def test_allows_prompt_workflow_output_without_checklist_container() -> None:
    payload = {
        "last_assistant_message": (
            "overall_status: pass\n"
            "target_local_roots\n"
            "target_canonical_roots\n"
            "target_file_globs\n"
            "comparison_basis\n"
            "completion_boundary\n"
            "base_minimal_instruction_layer: true\n"
            "on_demand_skill_loading: true\n"
        ),
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""

def test_blocks_missing_context_control_signals() -> None:
    payload = {
        "last_assistant_message": (
            "overall_status: pass\n"
            + _full_checklist_rows()
            + "target_local_roots\n"
            + "target_canonical_roots\n"
            + "target_file_globs\n"
            + "comparison_basis\n"
            + "completion_boundary\n"
            + "base_minimal_instruction_layer: true\n"
        ),
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["decision"] == "block"
    assert "Runtime context-control preamble missing" in response["reason"]
    assert "on-demand skill loading" in response["reason"]

def test_blocks_ambiguous_scope_phrasing() -> None:
    payload = {
        "last_assistant_message": (
            "overall_status: pass\n"
            + _full_checklist_rows()
            + "scope block includes target_local_roots target_canonical_roots "
            + "target_file_globs comparison_basis completion_boundary "
            + "base_minimal_instruction_layer: true\n"
            + "on_demand_skill_loading: true\n"
            + "and applies to this session."
        ),
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["decision"] == "block"
    assert "Ambiguous scope phrasing detected" in response["reason"]

def _wrap_five_section_scaffold(inner_body: str) -> str:
    return (
        "<role>Test role sentence one.</role>\n"
        "<context>Test context sentence one.</context>\n"
        f"{inner_body}\n"
        "<constraints>Test constraints sentence one.</constraints>\n"
        "<output_format>Test output format sentence one.</output_format>\n"
    )


def _build_prompt_workflow_message_with_fenced_xml(fenced_xml_body: str) -> str:
    return (
        "Audit: pass 15/15\n"
        "```xml\n"
        + fenced_xml_body
        + "\n```\n"
        "overall_status: pass\n"
        + _full_checklist_rows()
        + "target_local_roots\n"
        "target_canonical_roots\n"
        "target_file_globs\n"
        "comparison_basis\n"
        "completion_boundary\n"
        "base_minimal_instruction_layer: true\n"
        "on_demand_skill_loading: true\n"
    )


def test_allows_positive_phrasing_inside_fenced_xml() -> None:
    fenced_content = _wrap_five_section_scaffold(
        "<instructions>Ensure all functions have explicit return types.</instructions>"
    )
    payload = {
        "last_assistant_message": _build_prompt_workflow_message_with_fenced_xml(fenced_content),
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""


BANNED_KEYWORD_TEST_CASES: list[tuple[str, str]] = [
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
]


@pytest.mark.parametrize(
    ("banned_pattern_name", "fenced_xml_content"),
    BANNED_KEYWORD_TEST_CASES,
    ids=[each_case[0] for each_case in BANNED_KEYWORD_TEST_CASES],
)
def test_blocks_banned_pattern_inside_fenced_xml(
    banned_pattern_name: str,
    fenced_xml_content: str,
) -> None:
    payload = {
        "last_assistant_message": _build_prompt_workflow_message_with_fenced_xml(
            _wrap_five_section_scaffold(fenced_xml_content)
        ),
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["decision"] == "block"


def test_permits_negative_keywords_outside_fenced_xml() -> None:
    fenced_inner = _wrap_five_section_scaffold(
        "<instructions>Ensure all functions have explicit return types.</instructions>"
    )
    message = (
        "Audit: pass 15/15\n"
        "Do not skip the audit line.\n"
        "```xml\n"
        + fenced_inner
        + "\n```\n"
        "overall_status: pass\n"
        + _full_checklist_rows()
        + "target_local_roots\n"
        "target_canonical_roots\n"
        "target_file_globs\n"
        "comparison_basis\n"
        "completion_boundary\n"
        "base_minimal_instruction_layer: true\n"
        "on_demand_skill_loading: true\n"
    )
    payload = {"last_assistant_message": message}
    result = _run_hook(payload)
    assert result.stdout.strip() == ""


def test_blocks_when_fenced_xml_missing_context_section() -> None:
    fenced_body = (
        "<role>Test role sentence one.</role>\n"
        "<instructions>Test instructions sentence one.</instructions>\n"
        "<constraints>Test constraints sentence one.</constraints>\n"
        "<output_format>Test output format sentence one.</output_format>\n"
    )
    payload = {
        "last_assistant_message": _build_prompt_workflow_message_with_fenced_xml(fenced_body),
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["decision"] == "block"
    assert "context" in response["reason"]
    assert "include all required XML sections" in response["systemMessage"]


def test_allows_fully_structured_prompt_workflow_output() -> None:
    payload = {
        "last_assistant_message": (
            "overall_status: pass\n"
            + _full_checklist_rows()
            + "target_local_roots\n"
            + "target_canonical_roots\n"
            + "target_file_globs\n"
            + "comparison_basis\n"
            + "completion_boundary\n"
            + "base_minimal_instruction_layer: true\n"
            + "on_demand_skill_loading: true\n"
        ),
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""
