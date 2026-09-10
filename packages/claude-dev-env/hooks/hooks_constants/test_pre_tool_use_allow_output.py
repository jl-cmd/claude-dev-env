"""Tests for the shared PreToolUse allow-with-rewrite stdout emitter."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from hooks_constants.pre_tool_use_allow_output import write_pre_tool_use_allow_to_stdout


def _emitted_payload(updated_tool_input: dict[str, object]) -> dict[str, object]:
    """Return the parsed payload the emitter wrote for one updated tool input."""
    captured_stdout = StringIO()
    with patch("sys.stdout", captured_stdout):
        write_pre_tool_use_allow_to_stdout(updated_tool_input)
    return json.loads(captured_stdout.getvalue())


def test_emitter_writes_an_allow_decision_carrying_the_updated_input() -> None:
    assert _emitted_payload({"command": "git status", "description": "check"}) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {"command": "git status", "description": "check"},
        }
    }
