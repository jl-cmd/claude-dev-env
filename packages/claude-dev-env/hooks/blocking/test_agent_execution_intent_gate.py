"""Tests for agent-execution-intent-gate hook."""

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).parent / "agent-execution-intent-gate.py"


def _run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def test_denies_task_without_explicit_intent_marker() -> None:
    payload = {
        "tool_name": "Task",
        "tool_input": {"prompt": "run the workflow", "description": "delegate"},
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "structured execution intent signal" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_allows_phrase_marker_with_scope_anchors() -> None:
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "prompt": (
                "execution_intent: explicit\n"
                "target_local_roots\n"
                "target_canonical_roots\n"
                "target_file_globs\n"
                "comparison_basis\n"
                "completion_boundary\n"
            ),
            "description": "explicit delegation intent",
        },
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""


def test_denies_when_scope_anchors_missing() -> None:
    payload = {
        "tool_name": "Agent",
        "tool_input": {
            "execution_intent": "explicit",
            "prompt": "target_local_roots only",
            "description": "delegate",
        },
    }
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Scope anchors missing" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_allows_when_intent_and_scope_anchors_present() -> None:
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "execution_intent_explicit": True,
            "description": "delegate",
            "prompt": (
                "target_local_roots\n"
                "target_canonical_roots\n"
                "target_file_globs\n"
                "comparison_basis\n"
                "completion_boundary\n"
            ),
        },
    }
    result = _run_hook(payload)
    assert result.stdout.strip() == ""

