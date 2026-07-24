#!/usr/bin/env python3
"""PreToolUse hook that keeps refactor-to-pass the default on a gate-blocked edit.

When an AskUserQuestion is about an edit a gate denied, this hook wants the
first option to read "Refactor to pass the gate (Recommended)". A question with
no gate wording passes untouched.

::

    question: "The gate denied this edit for a CODE_RULES violation. What now?"
    ok:   options[0] = "Refactor to pass the gate (Recommended)"
    flag: options[0] = "Write a skip token so the write goes through"

The trigger stays tight: the prose must hold "gate" and a block word before the
hook asks anything of the options.
"""

import json
import sys
from typing import TextIO

import _path_setup  # noqa: F401

from hooks_constants.gate_question_default_gate_constants import (
    ASK_USER_QUESTION_TOOL_NAME,
    GATE_QUESTION_DENY_MESSAGE,
    GATE_QUESTION_USER_NOTICE,
    GATE_TRIGGER_REQUIRED_PATTERN,
    GATE_TRIGGER_SUPPORTING_PATTERN,
    OPTION_LABEL_KEY,
    OPTIONS_KEY,
    PROSE_JOIN_SEPARATOR,
    QUESTION_TEXT_KEY,
    QUESTIONS_PAYLOAD_KEY,
    RECOMMENDED_LABEL_MARKER,
    REFACTOR_TO_PASS_LABEL_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin


def _collect_option_labels(question: dict) -> list[str]:
    """Return the label text of every well-formed option on a question."""
    all_options = question.get(OPTIONS_KEY, [])
    if not isinstance(all_options, list):
        return []
    all_labels: list[str] = []
    for each_option in all_options:
        if not isinstance(each_option, dict):
            continue
        option_label = each_option.get(OPTION_LABEL_KEY, "")
        if isinstance(option_label, str):
            all_labels.append(option_label)
    return all_labels


def _question_is_about_gate_block(
    question: dict, all_option_labels: list[str]
) -> bool:
    """Return True when the question prose names a gate and a block word.

    The prose is the question text joined with its option labels. Both a gate
    word and a supporting block word must appear, so an unrelated question never
    triggers the option checks.
    """
    prose_parts: list[str] = []
    question_text = question.get(QUESTION_TEXT_KEY, "")
    if isinstance(question_text, str):
        prose_parts.append(question_text)
    prose_parts.extend(all_option_labels)
    combined_prose = PROSE_JOIN_SEPARATOR.join(prose_parts)

    has_gate_word = GATE_TRIGGER_REQUIRED_PATTERN.search(combined_prose) is not None
    has_block_word = GATE_TRIGGER_SUPPORTING_PATTERN.search(combined_prose) is not None
    return has_gate_word and has_block_word


def _first_option_is_recommended_refactor(all_option_labels: list[str]) -> bool:
    """Return True when the first label reads as the recommended refactor choice."""
    if not all_option_labels:
        return False
    first_option_label = all_option_labels[0]
    is_refactor_choice = REFACTOR_TO_PASS_LABEL_PATTERN.search(first_option_label) is not None
    is_recommended = RECOMMENDED_LABEL_MARKER in first_option_label.lower()
    return is_refactor_choice and is_recommended


def _evaluate_question(question: object) -> str | None:
    """Return the deny reason for one gate question, or None to allow it."""
    if not isinstance(question, dict):
        return None
    all_option_labels = _collect_option_labels(question)
    if not _question_is_about_gate_block(question, all_option_labels):
        return None
    if _first_option_is_recommended_refactor(all_option_labels):
        return None
    return GATE_QUESTION_DENY_MESSAGE


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether an AskUserQuestion payload breaks the gate-default rule.

    Scans each question for gate wording and, on a match, wants the first
    option to be the recommended refactor choice.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        The permissionDecisionReason text when a gate question breaks the rule,
        or None when every question is allowed.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    raw_tool_input = payload_by_key.get("tool_input", {})
    if not isinstance(raw_tool_name, str) or not isinstance(raw_tool_input, dict):
        return None
    if raw_tool_name != ASK_USER_QUESTION_TOOL_NAME:
        return None

    all_questions = raw_tool_input.get(QUESTIONS_PAYLOAD_KEY, [])
    if not isinstance(all_questions, list):
        return None
    for each_question in all_questions:
        deny_reason = _evaluate_question(each_question)
        if deny_reason is not None:
            return deny_reason
    return None


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the full deny payload the hook writes for a deny-reason string.

    Args:
        deny_reason: The permissionDecisionReason text for the denial.

    Returns:
        The deny payload dictionary the hook serializes to stdout.
    """
    log_hook_block(
        calling_hook_name="gate_question_default_gate.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        },
        "systemMessage": GATE_QUESTION_USER_NOTICE,
        "suppressOutput": True,
    }


def _emit_deny(deny_reason: str, output_stream: TextIO) -> None:
    output_stream.write(json.dumps(build_deny_payload(deny_reason)))
    output_stream.flush()


def main() -> None:
    """Read the PreToolUse payload from stdin and block a gate question that breaks the rule."""
    payload_by_key = read_hook_input_dictionary_from_stdin()
    if payload_by_key is None:
        sys.exit(0)
    deny_reason = evaluate(payload_by_key)
    if deny_reason is not None:
        _emit_deny(deny_reason, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
