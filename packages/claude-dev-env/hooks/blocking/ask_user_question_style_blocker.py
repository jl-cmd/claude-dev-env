#!/usr/bin/env python3
"""PreToolUse hook: AskUserQuestion must lead with context in plain-brief style.

Each question field states a short fact first, then asks. Question and option
prose follow plain-brief wording: outcome first, short active sentences, no
process narration, no arrow chains, no stacked-hyphen jargon stacks.
Option descriptions are required so the user knows what each choice does.

See ``output-styles/plain-brief.md`` and the ask-user-question-required rule.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.ask_user_question_style_blocker_constants import (  # noqa: E402
    ALL_FINDING_GUIDANCE_BY_CODE,
    ALL_PERIOD_ABBREVIATIONS,
    ARROW_TOKEN_PATTERN,
    CALLING_HOOK_NAME,
    CLAUSE_SEPARATOR_PATTERN,
    CORRECTIVE_MESSAGE_FOOTER,
    CORRECTIVE_MESSAGE_HEADER,
    DENY_DECISION,
    FINDING_ARROW_CHAIN,
    FINDING_LONG_SENTENCE,
    FINDING_MISSING_CONTEXT,
    FINDING_MISSING_OPTION_DESCRIPTION,
    FINDING_PROCESS_NARRATION,
    FINDING_STACKED_HYPHEN_COMPOUND,
    FINDING_TOO_MANY_SENTENCES,
    HOOK_EVENT_NAME,
    MAXIMUM_SENTENCES_PER_OPTION_DESCRIPTION,
    MAXIMUM_SENTENCES_PER_QUESTION,
    MAXIMUM_WORDS_PER_SENTENCE,
    MINIMUM_ARROW_TOKENS_FOR_CHAIN,
    MINIMUM_CONTEXT_PREFIX_CHARACTER_COUNT,
    NEWLINE_JOIN_SEPARATOR,
    PROCESS_NARRATION_OPENER_PATTERN,
    STACKED_HYPHEN_COMPOUND_PATTERN,
    TERMINATOR_WITH_SPACE_PATTERN,
    TOKEN_BEFORE_TERMINATOR_PATTERN,
    TOOL_NAME,
    USER_FACING_NOTICE,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def _token_before_index(text: str, terminator_index: int) -> str:
    prefix = text[:terminator_index]
    token_match = TOKEN_BEFORE_TERMINATOR_PATTERN.search(prefix)
    if token_match is None:
        return ""
    return token_match.group(1)


def _is_abbreviation_terminator(text: str, terminator_index: int) -> bool:
    if text[terminator_index] != ".":
        return False
    token = _token_before_index(text, terminator_index)
    if not token:
        return False
    if token.lower() in ALL_PERIOD_ABBREVIATIONS:
        return True
    # Single-letter tokens ("U." / "e." in U.S. / e.g.) are not sentence ends.
    return len(token) == 1 and token.isalpha()


def _next_non_space_character(text: str, start_index: int) -> str:
    index = start_index
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text):
        return ""
    return text[index]


def _is_sentence_boundary(text: str, terminator_index: int) -> bool:
    """Return whether terminator_index is a real sentence end inside text."""
    if terminator_index < 0 or terminator_index >= len(text):
        return False
    terminator = text[terminator_index]
    if terminator not in ".!?":
        return False
    if _is_abbreviation_terminator(text, terminator_index):
        return False
    # Version tokens: digit.digit (no sentence end between version parts).
    if (
        terminator == "."
        and terminator_index > 0
        and text[terminator_index - 1].isdigit()
        and terminator_index + 1 < len(text)
        and text[terminator_index + 1].isdigit()
    ):
        return False
    following = _next_non_space_character(text, terminator_index + 1)
    if following == "":
        return True
    return following.isupper() or following in "\"'"


def _iter_statement_separator_ends(prefix: str) -> list[int]:
    """Return end indices of statement separators inside prefix (after whitespace)."""
    all_ends: list[int] = []
    for each_match in CLAUSE_SEPARATOR_PATTERN.finditer(prefix):
        all_ends.append(each_match.end())
    for each_match in TERMINATOR_WITH_SPACE_PATTERN.finditer(prefix):
        terminator_index = each_match.start()
        if not _is_sentence_boundary(prefix, terminator_index):
            continue
        all_ends.append(each_match.end())
    all_ends.sort()
    return all_ends


def question_has_leading_context(question_text: str) -> bool:
    """Return whether the question text puts a fact before the first ask.

    ::

        ok:   The gate blocks bare rm. How should temp cleanup run?
        ok:   The endpoint must use HTTPS. Which cert path should we take?
        flag: How should temp cleanup run?
        flag: Pick one? The gate failed. Which fix?

    Only the prefix before the first ``?`` counts. Abbreviations (``Dr.``,
    ``U.S.``, ``e.g.``) and version dots (``3.12``) are not statement ends.
    A later fact after a bare lead question does not rescue the call.

    Args:
        question_text: The AskUserQuestion ``question`` field.

    Returns:
        True when the prefix before the first ``?`` holds a statement
        separator and enough leading substance; False otherwise.
    """
    stripped_text = question_text.strip()
    if not stripped_text:
        return False
    first_question_mark_index = stripped_text.find("?")
    if first_question_mark_index < 0:
        return False
    prefix_before_question = stripped_text[:first_question_mark_index]
    for each_separator_end in _iter_statement_separator_ends(prefix_before_question):
        # Lead is text before the terminator character, not before trailing spaces.
        # Recover terminator by scanning back from separator end.
        cursor = each_separator_end - 1
        while cursor >= 0 and prefix_before_question[cursor].isspace():
            cursor -= 1
        if cursor < 0:
            continue
        lead_fact = prefix_before_question[:cursor].strip()
        if len(lead_fact) >= MINIMUM_CONTEXT_PREFIX_CHARACTER_COUNT:
            return True
    return False


def _record_finding(all_findings: list[str], finding_code: str) -> None:
    if finding_code not in all_findings:
        all_findings.append(finding_code)


def _split_sentences(prose_text: str) -> list[str]:
    stripped_text = prose_text.strip()
    if not stripped_text:
        return []
    all_sentences: list[str] = []
    sentence_start = 0
    index = 0
    while index < len(stripped_text):
        if stripped_text[index] in ".!?" and _is_sentence_boundary(stripped_text, index):
            following_start = index + 1
            while (
                following_start < len(stripped_text)
                and stripped_text[following_start].isspace()
            ):
                following_start += 1
            sentence = stripped_text[sentence_start:following_start].strip()
            if sentence:
                all_sentences.append(sentence)
            sentence_start = following_start
            index = following_start
            continue
        index += 1
    trailing = stripped_text[sentence_start:].strip()
    if trailing:
        all_sentences.append(trailing)
    return all_sentences


def _word_count(sentence_text: str) -> int:
    return len(sentence_text.split())


def _collect_length_findings(
    prose_text: str,
    maximum_sentence_count: int,
    all_findings: list[str],
) -> None:
    all_sentences = _split_sentences(prose_text)
    if len(all_sentences) > maximum_sentence_count:
        _record_finding(all_findings, FINDING_TOO_MANY_SENTENCES)
    for each_sentence in all_sentences:
        if _word_count(each_sentence) > MAXIMUM_WORDS_PER_SENTENCE:
            _record_finding(all_findings, FINDING_LONG_SENTENCE)
            break


def _collect_plain_brief_findings(prose_text: str, all_findings: list[str]) -> None:
    stripped_text = prose_text.strip()
    if PROCESS_NARRATION_OPENER_PATTERN.search(stripped_text) is not None:
        _record_finding(all_findings, FINDING_PROCESS_NARRATION)
    if len(ARROW_TOKEN_PATTERN.findall(prose_text)) >= MINIMUM_ARROW_TOKENS_FOR_CHAIN:
        _record_finding(all_findings, FINDING_ARROW_CHAIN)
    if STACKED_HYPHEN_COMPOUND_PATTERN.search(prose_text) is not None:
        _record_finding(all_findings, FINDING_STACKED_HYPHEN_COMPOUND)


def find_style_findings(tool_input: dict) -> list[str]:
    """Return ordered finding codes for AskUserQuestion tool input.

    Args:
        tool_input: The AskUserQuestion tool_input payload.

    Returns:
        Distinct finding codes in first-seen order; empty when the call is clean.
    """
    all_questions = tool_input.get("questions", [])
    if not isinstance(all_questions, list):
        return []

    all_findings: list[str] = []
    for each_question in all_questions:
        if not isinstance(each_question, dict):
            continue
        question_text = each_question.get("question", "")
        if not isinstance(question_text, str):
            question_text = ""

        if not question_has_leading_context(question_text):
            _record_finding(all_findings, FINDING_MISSING_CONTEXT)

        if question_text.strip():
            _collect_plain_brief_findings(question_text, all_findings)
            _collect_length_findings(
                question_text,
                MAXIMUM_SENTENCES_PER_QUESTION,
                all_findings,
            )

        all_options = each_question.get("options", [])
        if not isinstance(all_options, list):
            continue
        for each_option in all_options:
            if not isinstance(each_option, dict):
                continue
            option_description = each_option.get("description", "")
            if not isinstance(option_description, str) or not option_description.strip():
                _record_finding(all_findings, FINDING_MISSING_OPTION_DESCRIPTION)
                continue
            _collect_plain_brief_findings(option_description, all_findings)
            _collect_length_findings(
                option_description,
                MAXIMUM_SENTENCES_PER_OPTION_DESCRIPTION,
                all_findings,
            )

    return all_findings


def build_block_reason(all_findings: list[str]) -> str:
    """Return the deny reason naming each finding and its rewrite guidance.

    Args:
        all_findings: Ordered finding codes from ``find_style_findings``.

    Returns:
        The permissionDecisionReason text for the denial.
    """
    all_guidance_lines = [
        f"- {ALL_FINDING_GUIDANCE_BY_CODE[each_code]}"
        for each_code in all_findings
        if each_code in ALL_FINDING_GUIDANCE_BY_CODE
    ]
    blank_line = NEWLINE_JOIN_SEPARATOR + NEWLINE_JOIN_SEPARATOR
    return blank_line.join(
        [
            CORRECTIVE_MESSAGE_HEADER,
            NEWLINE_JOIN_SEPARATOR.join(all_guidance_lines),
            CORRECTIVE_MESSAGE_FOOTER,
        ]
    )


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the full deny payload for a deny-reason string.

    Args:
        deny_reason: The permissionDecisionReason text.

    Returns:
        The deny payload dictionary the hook serializes to stdout.
    """
    log_hook_block(
        calling_hook_name=CALLING_HOOK_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=deny_reason,
        tool_name=TOOL_NAME,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": DENY_DECISION,
            "permissionDecisionReason": deny_reason,
        },
        "systemMessage": USER_FACING_NOTICE,
        "suppressOutput": True,
    }


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether an AskUserQuestion payload fails style checks.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        The permissionDecisionReason text when denied, or None when allowed.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    raw_tool_input = payload_by_key.get("tool_input", {})
    if raw_tool_name != TOOL_NAME or not isinstance(raw_tool_input, dict):
        return None

    all_findings = find_style_findings(raw_tool_input)
    if not all_findings:
        return None
    return build_block_reason(all_findings)


def _emit_deny(deny_reason: str, output_stream: TextIO) -> None:
    output_stream.write(json.dumps(build_deny_payload(deny_reason)))
    output_stream.flush()


def main() -> None:
    input_data = read_hook_input_dictionary_from_stdin()
    if input_data is None:
        sys.exit(0)

    deny_reason = evaluate(input_data)
    if deny_reason is None:
        sys.exit(0)

    _emit_deny(deny_reason, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
