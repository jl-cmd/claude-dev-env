"""Tests for the shared PostToolUse context emitter."""

from __future__ import annotations

import json

import pytest

from hooks_constants.post_tool_use_context import write_post_tool_use_context_to_stdout


def test_should_write_the_post_tool_use_payload_carrying_the_context_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_post_tool_use_context_to_stdout("=== PR DONE CHECKLIST ===")

    assert json.loads(capsys.readouterr().out) == {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "=== PR DONE CHECKLIST ===",
        }
    }
