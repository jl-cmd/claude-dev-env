"""Payload-shape fixtures for the pure AskUserQuestion analyzer.

Grades lean-block shape without hook I/O. Each case names one marker or cap
the PR #720 contract preserves.
"""

from __future__ import annotations

import pathlib
import sys

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.ask_user_question_shape import (  # noqa: E402
    analyze_ask_user_question_shape,
    count_prose_words,
    find_question_block_violations,
    mask_inline_code,
    normalize_line_endings,
)
from hooks_constants.plain_language_blocker_constants import (  # noqa: E402
    MAXIMUM_OPTION_DESCRIPTION_WORD_COUNT,
    MAXIMUM_QUESTION_SENTENCE_COUNT,
    MAXIMUM_QUESTION_WORD_COUNT,
)

LEAN_QUESTION = "Which gate should run first?"
LEAN_DESCRIPTION = "Runs on every write."


def _ask_payload(
    question_text: str,
    all_descriptions: list[str],
) -> dict[str, object]:
    return {
        "questions": [
            {
                "question": question_text,
                "options": [
                    {"label": f"Option {each_index}", "description": each_description}
                    for each_index, each_description in enumerate(all_descriptions, start=1)
                ],
            }
        ]
    }


def test_lean_payload_is_clean() -> None:
    result = analyze_ask_user_question_shape(
        _ask_payload(LEAN_QUESTION, [LEAN_DESCRIPTION])
    )
    assert result.is_lean
    assert result.all_violations == ()


def test_list_marker_under_question_is_flagged() -> None:
    plan_question = f"{LEAN_QUESTION}\n- Split the file\n- Wire the gate"
    result = analyze_ask_user_question_shape(
        _ask_payload(plan_question, [LEAN_DESCRIPTION])
    )
    assert not result.is_lean
    assert any("list marker" in each for each in result.all_violations)


def test_fenced_block_is_flagged() -> None:
    fenced_question = f"{LEAN_QUESTION}\n```\nrun_gate()\n```"
    result = analyze_ask_user_question_shape(
        _ask_payload(fenced_question, [LEAN_DESCRIPTION])
    )
    assert any("fenced code block" in each for each in result.all_violations)


def test_second_paragraph_is_flagged() -> None:
    two_paragraph_question = f"{LEAN_QUESTION}\n\nThe write gate reads every file."
    result = analyze_ask_user_question_shape(
        _ask_payload(two_paragraph_question, [LEAN_DESCRIPTION])
    )
    assert any("more than one paragraph" in each for each in result.all_violations)


def test_carriage_return_paragraph_break_is_flagged() -> None:
    crlf_question = f"{LEAN_QUESTION}\r\n\r\nThe write gate reads every file."
    result = analyze_ask_user_question_shape(
        _ask_payload(crlf_question, [LEAN_DESCRIPTION])
    )
    assert any("more than one paragraph" in each for each in result.all_violations)


def test_heading_is_flagged() -> None:
    headed_question = f"{LEAN_QUESTION}\n## The write gate\nIt reads every file."
    result = analyze_ask_user_question_shape(
        _ask_payload(headed_question, [LEAN_DESCRIPTION])
    )
    assert any("heading" in each for each in result.all_violations)


def test_table_row_in_option_is_flagged() -> None:
    result = analyze_ask_user_question_shape(
        _ask_payload(LEAN_QUESTION, ["| gate | 12 ms |"])
    )
    assert any("table row" in each for each in result.all_violations)


def test_question_over_word_cap_is_flagged() -> None:
    over_cap = " ".join(["word"] * (MAXIMUM_QUESTION_WORD_COUNT + 1))
    result = analyze_ask_user_question_shape(_ask_payload(over_cap, [LEAN_DESCRIPTION]))
    assert any("word" in each and "cap" in each for each in result.all_violations)


def test_question_over_sentence_cap_is_flagged() -> None:
    three_sentences = "One. Two. Three."
    assert MAXIMUM_QUESTION_SENTENCE_COUNT < 3
    result = analyze_ask_user_question_shape(
        _ask_payload(three_sentences, [LEAN_DESCRIPTION])
    )
    assert any("sentence" in each and "cap" in each for each in result.all_violations)


def test_option_description_over_word_cap_is_flagged() -> None:
    over_cap = " ".join(["word"] * (MAXIMUM_OPTION_DESCRIPTION_WORD_COUNT + 1))
    result = analyze_ask_user_question_shape(_ask_payload(LEAN_QUESTION, [over_cap]))
    assert any(
        "option description" in each and "word" in each for each in result.all_violations
    )


def test_option_description_over_sentence_cap_is_flagged() -> None:
    result = analyze_ask_user_question_shape(
        _ask_payload(LEAN_QUESTION, ["Runs on write. Reads every file."])
    )
    assert any(
        "option description" in each and "sentence" in each
        for each in result.all_violations
    )


def test_inline_code_counts_as_one_word() -> None:
    masked = mask_inline_code("Does `git diff --cached --stat` list it?")
    assert count_prose_words(masked) == count_prose_words("Does code list it?")


def test_normalize_line_endings_folds_crlf() -> None:
    assert normalize_line_endings("a\r\nb\rc") == "a\nb\nc"


def test_duplicate_faults_report_once() -> None:
    tool_input: dict[str, object] = {
        "questions": [
            {
                "question": LEAN_QUESTION,
                "options": [
                    {"label": "A", "description": "| a | b |"},
                    {"label": "B", "description": "| c | d |"},
                ],
            }
        ]
    }
    all_violations = find_question_block_violations(tool_input)
    table_faults = [each for each in all_violations if "table row" in each]
    assert len(table_faults) == 1


def test_non_dict_questions_list_is_clean() -> None:
    result = analyze_ask_user_question_shape({"questions": "not-a-list"})
    assert result.is_lean
