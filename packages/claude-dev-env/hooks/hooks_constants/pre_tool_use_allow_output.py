"""Shared stdout emitter for PreToolUse hooks that allow a rewritten tool input."""

from __future__ import annotations

import json
import sys

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
    ALLOW_DECISION,
    HOOK_EVENT_NAME,
)

__all__ = [
    "HOOK_SPECIFIC_OUTPUT_KEY",
    "HOOK_EVENT_NAME_KEY",
    "PERMISSION_DECISION_KEY",
    "UPDATED_INPUT_KEY",
    "write_pre_tool_use_allow_to_stdout",
]

HOOK_SPECIFIC_OUTPUT_KEY: str = "hookSpecificOutput"
HOOK_EVENT_NAME_KEY: str = "hookEventName"
PERMISSION_DECISION_KEY: str = "permissionDecision"
UPDATED_INPUT_KEY: str = "updatedInput"


def write_pre_tool_use_allow_to_stdout(
    all_updated_tool_input_fields: dict[str, object],
) -> None:
    """Write one PreToolUse allow payload carrying a rewritten tool input.

    A rewriter writes its replacement input here and the Bash PreToolUse
    dispatcher reads it back, carrying the updatedInput through to the harness.
    Both ends of that hop share this one payload shape rather than each holding
    a copy of it.

    Args:
        all_updated_tool_input_fields: The full tool_input the tool call should run with.
    """
    payload = {
        HOOK_SPECIFIC_OUTPUT_KEY: {
            HOOK_EVENT_NAME_KEY: HOOK_EVENT_NAME,
            PERMISSION_DECISION_KEY: ALLOW_DECISION,
            UPDATED_INPUT_KEY: all_updated_tool_input_fields,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
