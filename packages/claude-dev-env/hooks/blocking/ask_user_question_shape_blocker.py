#!/usr/bin/env python3
"""PreToolUse hook that enforces AskUserQuestion field shape."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.ask_user_question_shape import (  # noqa: E402
    analyze_ask_user_question_shape,
)
from hooks_constants.ask_user_question_shape_constants import (  # noqa: E402
    ASK_USER_QUESTION_TOOL_NAME,
    LEAN_QUESTION_BLOCK_GUIDANCE,
    LEAN_QUESTION_BLOCK_PREFIX,
    LEAN_QUESTION_VIOLATION_SEPARATOR,
    USER_FACING_LEAN_QUESTION_NOTICE,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402


def build_lean_block_reason(all_violations: Sequence[str]) -> str:
    """Build a deny reason that names each field-shape violation."""
    violation_list = LEAN_QUESTION_VIOLATION_SEPARATOR.join(all_violations)
    return f"{LEAN_QUESTION_BLOCK_PREFIX}{violation_list}. {LEAN_QUESTION_BLOCK_GUIDANCE}"


def evaluate(payload_by_key: Mapping[str, object]) -> str | None:
    """Return a deny reason when an AskUserQuestion payload breaks field shape."""
    tool_name = payload_by_key.get("tool_name", "")
    tool_input = payload_by_key.get("tool_input", {})
    if tool_name != ASK_USER_QUESTION_TOOL_NAME:
        return None
    if not isinstance(tool_input, Mapping):
        return None
    shape_result = analyze_ask_user_question_shape(tool_input)
    if shape_result.is_lean:
        return None
    return build_lean_block_reason(shape_result.all_violations)


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the standard PreToolUse deny payload for a shape violation."""
    log_hook_block(
        calling_hook_name="ask_user_question_shape_blocker.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        },
        "systemMessage": USER_FACING_LEAN_QUESTION_NOTICE,
        "suppressOutput": True,
    }


def main() -> None:
    """Read one PreToolUse payload and deny malformed question shape."""
    try:
        payload_by_key = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(payload_by_key, dict):
        sys.exit(0)
    deny_reason = evaluate(payload_by_key)
    if deny_reason is None:
        sys.exit(0)
    sys.stdout.write(json.dumps(build_deny_payload(deny_reason)))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
