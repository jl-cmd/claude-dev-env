#!/usr/bin/env python3
"""Stop hook gate for prompt-workflow leakage and deterministic audit coverage."""

from __future__ import annotations

import json
import sys

from prompt_workflow_gate_core import (
    find_ambiguous_scope_terms,
    has_debug_intent,
    has_checklist_container,
    has_internal_object_leak,
    is_prompt_workflow_response,
    missing_checklist_rows,
    missing_scope_anchors,
)


def _extract_user_context(hook_input: dict) -> str:
    candidates = (
        "last_user_message",
        "user_message",
        "user_prompt",
        "prompt",
        "input",
    )
    for key in candidates:
        value = hook_input.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _build_block(reason: str) -> dict:
    return {
        "decision": "block",
        "reason": reason,
    }


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    assistant_message = str(hook_input.get("last_assistant_message", ""))
    if not assistant_message.strip():
        sys.exit(0)

    user_context = _extract_user_context(hook_input)
    debug_requested = has_debug_intent(user_context)

    if has_internal_object_leak(assistant_message) and not debug_requested:
        print(
            json.dumps(
                _build_block(
                    "PROMPT-WORKFLOW GATE: Raw internal refinement object leakage detected. "
                    "Return sanitized user-facing output unless explicit debug intent is present."
                )
            )
        )
        sys.exit(0)

    if is_prompt_workflow_response(assistant_message):
        if not has_checklist_container(assistant_message):
            print(
                json.dumps(
                    _build_block(
                        "PROMPT-WORKFLOW GATE: Deterministic checklist container missing. "
                        "Include `checklist_results` with all required rows."
                    )
                )
            )
            sys.exit(0)

        missing_rows = missing_checklist_rows(assistant_message)
        if missing_rows:
            print(
                json.dumps(
                    _build_block(
                        "PROMPT-WORKFLOW GATE: Deterministic checklist rows missing: "
                        + ", ".join(missing_rows)
                    )
                )
            )
            sys.exit(0)

        missing_anchors = missing_scope_anchors(assistant_message)
        if missing_anchors:
            print(
                json.dumps(
                    _build_block(
                        "PROMPT-WORKFLOW GATE: Required scope anchors missing: "
                        + ", ".join(missing_anchors)
                    )
                )
            )
            sys.exit(0)

        ambiguous_terms = find_ambiguous_scope_terms(assistant_message)
        if ambiguous_terms:
            print(
                json.dumps(
                    _build_block(
                        "PROMPT-WORKFLOW GATE: Ambiguous scope phrasing detected: "
                        + ", ".join(ambiguous_terms)
                    )
                )
            )
            sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
