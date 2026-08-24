"""Production-path tests for the AskUserQuestion shape hook."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent / "ask_user_question_shape_blocker.py"


def _payload(question_text: str, option_description: str) -> dict[str, object]:
    return {
        "tool_name": "AskUserQuestion",
        "tool_input": {
            "questions": [
                {
                    "question": question_text,
                    "header": "Gate",
                    "options": [{"label": "Run", "description": option_description}],
                }
            ]
        },
    }


def _run_hook(payload_by_key: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload_by_key),
        capture_output=True,
        text=True,
        check=False,
    )


def test_lean_question_passes_through_the_runtime_hook() -> None:
    completed = _run_hook(_payload("Which gate should run first?", "Runs on write."))

    assert completed.returncode == 0
    assert completed.stdout == ""


def test_question_with_list_detail_is_denied_by_the_runtime_hook() -> None:
    completed = _run_hook(
        _payload(
            "Which gate should run first?\n- Write\n- Commit",
            "Runs on write.",
        )
    )

    parsed_payload = json.loads(completed.stdout)
    hook_specific_output = parsed_payload["hookSpecificOutput"]
    assert hook_specific_output["permissionDecision"] == "deny"
    assert "list marker" in hook_specific_output["permissionDecisionReason"]
    assert "question" in parsed_payload["systemMessage"].lower()


def test_non_question_tool_passes_through_the_runtime_hook() -> None:
    completed = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "notes.md", "content": "Text."},
        }
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
