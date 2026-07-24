"""Tests for the ask_user_question_style_blocker PreToolUse hook.

Covers context-before-question, option descriptions, and plain-brief wording
checks (process openers, arrow chains, stacked-hyphen compounds, length caps).
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest import mock

HOOK_SCRIPT_PATH = Path(__file__).parent / "ask_user_question_style_blocker.py"
_HOOKS_DIR = str(Path(__file__).resolve().parent)
_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)

from hooks_constants.ask_user_question_style_blocker_constants import (  # noqa: E402
    FINDING_ARROW_CHAIN,
    FINDING_LONG_SENTENCE,
    FINDING_MISSING_CONTEXT,
    FINDING_MISSING_OPTION_DESCRIPTION,
    FINDING_PROCESS_NARRATION,
    FINDING_STACKED_HYPHEN_COMPOUND,
    FINDING_TOO_MANY_SENTENCES,
    PLAIN_BRIEF_STYLE_PATH,
    TOOL_NAME,
)


def _load_hook_module() -> object:
    module_spec = importlib.util.spec_from_file_location(
        "ask_user_question_style_blocker_under_test", HOOK_SCRIPT_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


hook_module = _load_hook_module()
evaluate = hook_module.evaluate
find_style_findings = hook_module.find_style_findings
question_has_leading_context = hook_module.question_has_leading_context

CLEAN_QUESTION_TEXT = (
    "The gate blocks bare rm on worktrees. How should temp cleanup run?"
)


def _payload(question: str, all_options: list[dict[str, str]] | None = None) -> dict:
    if all_options is None:
        all_options = [
            {"label": "Yes", "description": "Apply the change now."},
            {"label": "No", "description": "Leave the current path alone."},
        ]
    return {
        "tool_name": TOOL_NAME,
        "tool_input": {
            "questions": [
                {
                    "question": question,
                    "header": "Choice",
                    "options": all_options,
                }
            ]
        },
    }


def _run_main(payload: dict) -> str:
    with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            try:
                hook_module.main()
            except SystemExit:
                pass
            return mock_stdout.getvalue()


def test_bare_question_without_context_is_flagged() -> None:
    assert question_has_leading_context("Which path should we take?") is False
    findings = find_style_findings(_payload("Which path should we take?")["tool_input"])
    assert FINDING_MISSING_CONTEXT in findings


def test_fact_then_question_passes_context_check() -> None:
    assert question_has_leading_context(CLEAN_QUESTION_TEXT) is True
    findings = find_style_findings(_payload(CLEAN_QUESTION_TEXT)["tool_input"])
    assert FINDING_MISSING_CONTEXT not in findings


def test_colon_separated_context_passes() -> None:
    question_text = "Two paths are open: ship the fix now, or wait for review?"
    assert question_has_leading_context(question_text) is True


def test_context_after_first_question_mark_does_not_count() -> None:
    question_text = "Pick one? The gate blocks bare rm. Which cleanup should run?"
    assert question_has_leading_context(question_text) is False


def test_version_token_dot_is_not_context_separator() -> None:
    question_text = "Should we use Python 3.12 for the hook runtime now?"
    assert question_has_leading_context(question_text) is False


def test_abbreviation_in_lead_fact_still_allows_context() -> None:
    question_text = (
        "The U.S. gate blocks bare rm on worktrees. How should temp cleanup run?"
    )
    assert question_has_leading_context(question_text) is True


def test_uppercase_acronym_sentence_end_counts_as_context() -> None:
    question_text = "The endpoint must use HTTPS. Which cert path should we take?"
    assert question_has_leading_context(question_text) is True


def test_eg_abbreviation_does_not_steal_context() -> None:
    question_text = (
        "See e.g. the bare-rm gate docs. How should temp cleanup run?"
    )
    assert question_has_leading_context(question_text) is True


def test_doctor_title_does_not_inflate_sentence_count() -> None:
    question_text = (
        "Dr. Smith blocked the write. Mr. Lee wants a defer. "
        "Which path should we take?"
    )
    findings = find_style_findings(_payload(question_text)["tool_input"])
    assert FINDING_MISSING_CONTEXT not in findings
    assert FINDING_TOO_MANY_SENTENCES not in findings


def test_etc_ending_fact_still_counts_as_context() -> None:
    question_text = "We need cleanup, backups, etc. How should temp cleanup run?"
    assert question_has_leading_context(question_text) is True


def test_parenthetical_sentence_still_counts_as_context() -> None:
    question_text = (
        "The gate failed. (See the logs.) Which path should we take?"
    )
    assert question_has_leading_context(question_text) is True


def test_numbered_list_markers_do_not_inflate_sentence_count() -> None:
    question_text = (
        "1. The gate failed on ruff. 2. Tests also failed. "
        "Which fix should land first?"
    )
    findings = find_style_findings(_payload(question_text)["tool_input"])
    assert FINDING_MISSING_CONTEXT not in findings
    assert FINDING_TOO_MANY_SENTENCES not in findings


def test_missing_option_description_is_flagged() -> None:
    findings = find_style_findings(
        _payload(
            "The deploy failed on ruff. Which fix should land first?",
            all_options=[
                {"label": "Fix ruff", "description": ""},
                {"label": "Skip", "description": "Leave the failure for later."},
            ],
        )["tool_input"]
    )
    assert FINDING_MISSING_OPTION_DESCRIPTION in findings


def test_process_narration_in_option_description_is_flagged() -> None:
    findings = find_style_findings(
        _payload(
            CLEAN_QUESTION_TEXT,
            all_options=[
                {
                    "label": "Yes",
                    "description": "I looked at the logs and would switch now.",
                },
                {"label": "No", "description": "Leave the current path alone."},
            ],
        )["tool_input"]
    )
    assert FINDING_PROCESS_NARRATION in findings


def test_too_many_option_description_sentences_is_flagged() -> None:
    findings = find_style_findings(
        _payload(
            CLEAN_QUESTION_TEXT,
            all_options=[
                {
                    "label": "Yes",
                    "description": "Apply the change now. Ship today. Notify the team after.",
                },
                {"label": "No", "description": "Leave the current path alone."},
            ],
        )["tool_input"]
    )
    assert FINDING_TOO_MANY_SENTENCES in findings


def test_process_narration_opener_is_flagged() -> None:
    question_text = (
        "I looked at the gate and it blocks bare rm. How should temp cleanup run?"
    )
    findings = find_style_findings(_payload(question_text)["tool_input"])
    assert FINDING_PROCESS_NARRATION in findings


def test_arrow_chain_is_flagged() -> None:
    question_text = (
        "The flow is setup → check → fail on bare rm. How should temp cleanup run?"
    )
    findings = find_style_findings(_payload(question_text)["tool_input"])
    assert FINDING_ARROW_CHAIN in findings


def test_stacked_hyphen_compound_is_flagged() -> None:
    question_text = (
        "The hash-bound fail-closed release-gate contract blocks the write. "
        "Which path should we take?"
    )
    findings = find_style_findings(_payload(question_text)["tool_input"])
    assert FINDING_STACKED_HYPHEN_COMPOUND in findings


def test_long_sentence_is_flagged() -> None:
    long_sentence = (
        "The gate that currently blocks every bare removal command aimed at a "
        "worktree path including nested temporary directories and scratch folders "
        "also blocks the only cleanup form that would safely clear the probe files "
        "we create during a run when the parent never removes them."
    )
    question_text = f"{long_sentence} How should temp cleanup run?"
    findings = find_style_findings(_payload(question_text)["tool_input"])
    assert FINDING_LONG_SENTENCE in findings


def test_too_many_question_sentences_is_flagged() -> None:
    question_text = (
        "The gate blocks bare rm. Worktrees stay dirty. Probe files linger. "
        "Temp dirs pile up. How should temp cleanup run?"
    )
    findings = find_style_findings(_payload(question_text)["tool_input"])
    assert FINDING_TOO_MANY_SENTENCES in findings


def test_clean_question_has_no_findings() -> None:
    findings = find_style_findings(_payload(CLEAN_QUESTION_TEXT)["tool_input"])
    assert findings == []


def test_evaluate_denies_bare_question() -> None:
    deny_reason = evaluate(_payload("Should we proceed?"))
    assert deny_reason is not None
    assert "ASK_USER_QUESTION_STYLE" in deny_reason
    assert PLAIN_BRIEF_STYLE_PATH in deny_reason


def test_evaluate_allows_clean_question() -> None:
    deny_reason = evaluate(_payload(CLEAN_QUESTION_TEXT))
    assert deny_reason is None


def test_main_denies_and_emits_payload() -> None:
    output_text = _run_main(_payload("Which path?"))
    assert output_text
    parsed = json.loads(output_text)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "ASK_USER_QUESTION_STYLE" in parsed["hookSpecificOutput"]["permissionDecisionReason"]


def test_main_allows_clean_payload_silently() -> None:
    output_text = _run_main(_payload(CLEAN_QUESTION_TEXT))
    assert output_text == ""


def test_non_ask_user_question_tool_is_ignored() -> None:
    deny_reason = evaluate(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "x.md", "content": "Which path?"},
        }
    )
    assert deny_reason is None
