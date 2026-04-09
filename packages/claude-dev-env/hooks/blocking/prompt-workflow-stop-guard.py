#!/usr/bin/env python3
"""Stop hook gate for prompt-workflow leakage and deterministic audit coverage."""

from __future__ import annotations

import datetime
import json
import sys
from collections.abc import Callable
from pathlib import Path

from prompt_workflow_gate_core import (
    find_ambiguous_scope_terms,
    find_negative_keywords_in_fenced_xml,
    has_debug_intent,
    has_checklist_container,
    has_internal_object_leak,
    is_prompt_workflow_response,
    missing_context_control_signals,
    missing_checklist_rows,
    missing_scope_anchors,
)

PROMPT_GATE_LOG_PATH: Path = Path.home() / ".claude" / "logs" / "prompt-gate.log"
USER_FACING_PREFIX: str = "[prompt-gate]"

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

def _append_diagnostic_to_log(brief_label: str, full_reason: str) -> None:
    try:
        PROMPT_GATE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        timestamp_iso = datetime.datetime.now().isoformat()
        log_entry = f"{timestamp_iso}\t{brief_label}\t{full_reason}\n"
        with PROMPT_GATE_LOG_PATH.open("a", encoding="utf-8") as log_handle:
            log_handle.write(log_entry)
    except OSError:
        pass

def _build_block(brief_label: str, full_reason: str) -> dict:
    _append_diagnostic_to_log(brief_label, full_reason)
    return {
        "decision": "block",
        "reason": full_reason,
        "systemMessage": f"{USER_FACING_PREFIX} {brief_label}",
        "suppressOutput": True,
    }

def _check_internal_object_leak(
    assistant_message: str,
    debug_requested: bool,
) -> dict | None:
    if not has_internal_object_leak(assistant_message) or debug_requested:
        return None
    return _build_block(
        brief_label="retrying: sanitize audit format",
        full_reason=(
            "PROMPT-WORKFLOW GATE: Raw internal refinement object leakage detected. "
            "Return sanitized user-facing output unless explicit debug intent is present."
        ),
    )

def _check_checklist_container(assistant_message: str) -> dict | None:
    if has_checklist_container(assistant_message):
        return None
    return _build_block(
        brief_label="retrying: add checklist",
        full_reason=(
            "PROMPT-WORKFLOW GATE: Deterministic checklist container missing. "
            "Include `checklist_results` with all required rows."
        ),
    )

def _check_missing_checklist_rows(assistant_message: str) -> dict | None:
    if not has_checklist_container(assistant_message):
        return None
    missing_rows = missing_checklist_rows(assistant_message)
    if not missing_rows:
        return None
    return _build_block(
        brief_label="retrying: complete checklist",
        full_reason=(
            "PROMPT-WORKFLOW GATE: Deterministic checklist rows missing: "
            + ", ".join(missing_rows)
        ),
    )

def _check_missing_scope_anchors(assistant_message: str) -> dict | None:
    missing_anchors = missing_scope_anchors(assistant_message)
    if not missing_anchors:
        return None
    return _build_block(
        brief_label="retrying: add scope anchors",
        full_reason=(
            "PROMPT-WORKFLOW GATE: Required scope anchors missing: "
            + ", ".join(missing_anchors)
        ),
    )

def _check_missing_context_signals(assistant_message: str) -> dict | None:
    missing_signals = missing_context_control_signals(assistant_message)
    if not missing_signals:
        return None
    return _build_block(
        brief_label="retrying: add runtime signals",
        full_reason=(
            "PROMPT-WORKFLOW GATE: Runtime context-control preamble missing. "
            "Include the two required lines from prompt-workflow-context-controls "
            "(minimal instruction layer and on-demand skill loading)."
        ),
    )

def _check_ambiguous_scope(assistant_message: str) -> dict | None:
    ambiguous_terms = find_ambiguous_scope_terms(assistant_message)
    if not ambiguous_terms:
        return None
    return _build_block(
        brief_label="retrying: rephrase scope refs",
        full_reason=(
            "PROMPT-WORKFLOW GATE: Ambiguous scope phrasing detected: "
            + ", ".join(ambiguous_terms)
        ),
    )

def _check_negative_keywords_in_artifact(assistant_message: str) -> dict | None:
    violations = find_negative_keywords_in_fenced_xml(assistant_message)
    if not violations:
        return None
    violation_descriptions = [
        f"  line {each_violation['line_number']}: \"{each_violation['keyword']}\" in: {each_violation['line_text']}"
        for each_violation in violations
    ]
    return _build_block(
        brief_label="retrying: rephrase negative keywords in artifact",
        full_reason=(
            "PROMPT-WORKFLOW GATE: Banned negative keywords found inside fenced XML artifact. "
            "Rephrase as positive directives (what TO do, not what to avoid):\n"
            + "\n".join(violation_descriptions)
        ),
    )

def _evaluate_workflow_gates(assistant_message: str) -> dict | None:
    if not is_prompt_workflow_response(assistant_message):
        return None
    workflow_gate_checks: tuple[Callable[[str], dict | None], ...] = (
        _check_missing_checklist_rows,
        _check_missing_scope_anchors,
        _check_missing_context_signals,
        _check_ambiguous_scope,
        _check_negative_keywords_in_artifact,
    )
    for check in workflow_gate_checks:
        block = check(assistant_message)
        if block is not None:
            return block
    return None

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

    block = _check_internal_object_leak(assistant_message, debug_requested)
    if block is None:
        block = _evaluate_workflow_gates(assistant_message)

    if block is not None:
        sys.stdout.write(json.dumps(block) + "\n")

    sys.exit(0)

if __name__ == "__main__":
    main()
