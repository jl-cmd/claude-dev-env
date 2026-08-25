"""Production-path tests for the AskUserQuestion plain-language blocker."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).with_name("plain_language_blocker.py")


def _run_hook(
    payload: dict[str, object], *, enabled: bool
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if enabled:
        environment["CLAUDE_PROSE_STYLE_ENFORCEMENT"] = "1"
    else:
        environment.pop("CLAUDE_PROSE_STYLE_ENFORCEMENT", None)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )


def _decision(result: subprocess.CompletedProcess[str]) -> str | None:
    if not result.stdout:
        return None
    parsed_payload = json.loads(result.stdout)
    return parsed_payload.get("hookSpecificOutput", {}).get("permissionDecision")


def test_default_off_allows_formal_question_word() -> None:
    result = _run_hook(
        {
            "tool_name": "AskUserQuestion",
            "tool_input": {
                "questions": [{"question": "Should we utilize this path?"}]
            },
        },
        enabled=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_enabled_blocks_formal_question_word() -> None:
    result = _run_hook(
        {
            "tool_name": "AskUserQuestion",
            "tool_input": {
                "questions": [
                    {
                        "question": "Should we utilize this path?",
                        "options": [{"description": "Initiate the migration."}],
                    }
                ]
            },
        },
        enabled=True,
    )
    assert result.returncode == 0
    assert _decision(result) == "deny"
    assert "utilize -> use" in result.stdout
    assert "initiate -> start" in result.stdout


def test_exact_code_url_and_path_text_is_exempt() -> None:
    result = _run_hook(
        {
            "tool_name": "AskUserQuestion",
            "tool_input": {
                "questions": [
                    {
                        "question": (
                            "Use `utilize` in src/initiate.py or "
                            "https://example.test/utilize."
                        )
                    }
                ]
            },
        },
        enabled=True,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_other_tools_are_ignored() -> None:
    result = _run_hook(
        {
            "tool_name": "Write",
            "tool_input": {"content": "Utilize the existing helper."},
        },
        enabled=True,
    )
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize("raw_input", ["", "[]", "not json"])
def test_invalid_input_is_fail_open(raw_input: str) -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=raw_input,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout == ""
