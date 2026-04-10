#!/usr/bin/env python3
"""Shared prompt-workflow validator callable from tests, CLI, and the Stop hook.

Public API
----------
validate_prompt_workflow(assistant_message, user_context="")
    Returns a ``ValidationResult`` with allowed/blocked status and reasons.

CLI
---
    python prompt_workflow_validate.py path/to/draft.md
    cat draft.md | python prompt_workflow_validate.py

Exit codes match hook conventions: 0 allowed, 2 blocked.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from prompt_workflow_gate_core import (
    find_ambiguous_scope_terms,
    find_negative_keywords_in_fenced_xml,
    has_checklist_container,
    has_debug_intent,
    has_internal_object_leak,
    is_prompt_workflow_response,
    missing_checklist_rows,
    missing_context_control_signals,
    missing_required_xml_sections,
    missing_scope_anchors,
)

@dataclass(frozen=True)
class ValidationReason:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    reasons: tuple[ValidationReason, ...] = field(default_factory=tuple)

    @property
    def reason_messages(self) -> list[str]:
        return [each_reason.message for each_reason in self.reasons]

    @property
    def reason_codes(self) -> list[str]:
        return [each_reason.code for each_reason in self.reasons]


def _blocked(code: str, message: str) -> ValidationResult:
    return ValidationResult(
        allowed=False,
        reasons=(ValidationReason(code=code, message=message),),
    )


def _check_internal_leak(
    assistant_message: str,
    debug_requested: bool,
) -> ValidationResult | None:
    if not has_internal_object_leak(assistant_message) or debug_requested:
        return None
    return _blocked(
        code="internal_object_leak",
        message=(
            "Raw internal refinement object leakage detected. "
            "Return sanitized user-facing output unless explicit debug intent is present."
        ),
    )


def _check_required_sections(assistant_message: str) -> ValidationResult | None:
    missing_sections = missing_required_xml_sections(assistant_message)
    if not missing_sections:
        return None
    return _blocked(
        code="missing_xml_sections",
        message=(
            "Fenced XML artifact missing required sections: "
            + ", ".join(missing_sections)
        ),
    )


def _check_checklist_rows(assistant_message: str) -> ValidationResult | None:
    if not has_checklist_container(assistant_message):
        return None
    missing_rows = missing_checklist_rows(assistant_message)
    if not missing_rows:
        return None
    return _blocked(
        code="missing_checklist_rows",
        message=("Deterministic checklist rows missing: " + ", ".join(missing_rows)),
    )


def _check_scope_anchors(assistant_message: str) -> ValidationResult | None:
    missing_anchors = missing_scope_anchors(assistant_message)
    if not missing_anchors:
        return None
    return _blocked(
        code="missing_scope_anchors",
        message=("Required scope anchors missing: " + ", ".join(missing_anchors)),
    )


def _check_context_signals(assistant_message: str) -> ValidationResult | None:
    missing_signals = missing_context_control_signals(assistant_message)
    if not missing_signals:
        return None
    return _blocked(
        code="missing_context_signals",
        message=(
            "Runtime context-control preamble missing. "
            "Include the two required lines from prompt-workflow-context-controls "
            "(minimal instruction layer and on-demand skill loading)."
        ),
    )


def _check_ambiguous_scope(assistant_message: str) -> ValidationResult | None:
    ambiguous_terms = find_ambiguous_scope_terms(assistant_message)
    if not ambiguous_terms:
        return None
    return _blocked(
        code="ambiguous_scope",
        message=("Ambiguous scope phrasing detected: " + ", ".join(ambiguous_terms)),
    )


def _check_negative_keywords(assistant_message: str) -> ValidationResult | None:
    violations = find_negative_keywords_in_fenced_xml(assistant_message)
    if not violations:
        return None
    violation_descriptions = [
        f"  line {each_violation['line_number']}: "
        f'"{each_violation["keyword"]}" in: {each_violation["line_text"]}'
        for each_violation in violations
    ]
    return _blocked(
        code="negative_keywords_in_artifact",
        message=(
            "Banned negative keywords found inside fenced XML artifact. "
            "Rephrase as positive directives (what TO do, not what to avoid):\n"
            + "\n".join(violation_descriptions)
        ),
    )


def validate_prompt_workflow(
    assistant_message: str,
    user_context: str = "",
) -> ValidationResult:
    """Run all prompt-workflow gates on *assistant_message*.

    Returns ``ValidationResult.allowed == True`` when every gate passes.
    The first failing gate short-circuits and its reason is returned.
    """
    allowed_result = ValidationResult(allowed=True)

    if not assistant_message.strip():
        return allowed_result

    debug_requested = has_debug_intent(user_context)

    leak_result = _check_internal_leak(assistant_message, debug_requested)
    if leak_result is not None:
        return leak_result

    if not is_prompt_workflow_response(assistant_message):
        return allowed_result

    workflow_checks = (
        _check_required_sections,
        _check_checklist_rows,
        _check_scope_anchors,
        _check_context_signals,
        _check_ambiguous_scope,
        _check_negative_keywords,
    )
    for each_check in workflow_checks:
        gate_result = each_check(assistant_message)
        if gate_result is not None:
            return gate_result

    return allowed_result


def main() -> None:
    blocked_exit_code: int = 2
    allowed_exit_code: int = 0

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        assistant_text = file_path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        assistant_text = sys.stdin.read()
    else:
        sys.stderr.write("Usage: prompt_workflow_validate.py [path/to/draft.md]\n")
        sys.stderr.write("       cat draft.md | prompt_workflow_validate.py\n")
        sys.exit(blocked_exit_code)

    validation_result = validate_prompt_workflow(assistant_text)
    if validation_result.allowed:
        sys.exit(allowed_exit_code)
    for each_reason in validation_result.reasons:
        sys.stderr.write(f"[{each_reason.code}] {each_reason.message}\n")
    sys.exit(blocked_exit_code)


if __name__ == "__main__":
    main()
