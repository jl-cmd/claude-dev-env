#!/usr/bin/env python3
"""PreToolUse gate for Task/Agent execution intent and scope anchors."""

from __future__ import annotations

import json
import os
import sys

from prompt_workflow_gate_core import (
    has_explicit_execution_intent,
    has_structured_execution_intent,
    missing_scope_anchors,
)


def _deny(reason: str) -> None:
    response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(response))


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = str(hook_input.get("tool_name", ""))
    if tool_name not in {"Task", "Agent"}:
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    prompt_text = str(tool_input.get("prompt", ""))
    description = str(tool_input.get("description", ""))
    combined_text = f"{description}\n{prompt_text}"

    if not has_structured_execution_intent(tool_input):
        allow_text_fallback = os.getenv(
            "PROMPT_WORKFLOW_ALLOW_TEXT_INTENT_FALLBACK", ""
        ).strip().lower() in {"1", "true", "yes"}
        text_intent_detected = has_explicit_execution_intent(combined_text)
        if allow_text_fallback and text_intent_detected:
            print(
                "PROMPT-WORKFLOW GATE: compatibility text-intent fallback used; "
                "structured execution intent contract should be provided.",
                file=sys.stderr,
            )
        else:
            fallback_note = ""
            if text_intent_detected:
                print(
                    "PROMPT-WORKFLOW GATE: text intent marker detected without structured "
                    "execution intent contract.",
                    file=sys.stderr,
                )
                fallback_note = " Legacy text marker was detected but is not sufficient."
            _deny(
                "BLOCKED: Missing structured execution intent signal for Agent/Task launch. "
                "Provide `tool_input.execution_intent: explicit` or "
                "`tool_input.execution_intent_explicit: true`."
                + fallback_note
            )
            sys.exit(0)

    missing_anchors = missing_scope_anchors(combined_text)
    if missing_anchors:
        _deny(
            "BLOCKED: Scope anchors missing for prompt workflow execution: "
            + ", ".join(missing_anchors)
        )
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
