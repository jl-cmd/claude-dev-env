"""Tests for prompt-workflow-stop-guard hook."""

import json
import subprocess
import sys
from pathlib import Path


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


def test_blocks_missing_checklist_container_for_prompt_workflow_output() -> None:
    payload = {
        "last_assistant_message": (
            "overall_status: pass\n"
            "target_local_roots\n"
            "target_canonical_roots\n"
            "target_file_globs\n"
            "comparison_basis\n"
            "completion_boundary\n"
        ),
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["decision"] == "block"
    assert "Deterministic checklist container missing" in response["reason"]


def test_blocks_ambiguous_scope_phrasing() -> None:
    payload = {
        "last_assistant_message": (
            "overall_status: pass\n"
            + _full_checklist_rows()
            + "scope block includes target_local_roots target_canonical_roots "
            + "target_file_globs comparison_basis completion_boundary "
            + "and applies to this session."
        ),
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["decision"] == "block"
    assert "Ambiguous scope phrasing detected" in response["reason"]


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
        ),
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""
