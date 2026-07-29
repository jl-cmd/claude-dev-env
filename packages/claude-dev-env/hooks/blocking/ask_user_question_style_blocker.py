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
    ALL_BROAD_QUESTION_SENTENCE_OPENERS,
    ALL_FINDING_GUIDANCE_BY_CODE,
    ALL_QUESTION_SENTENCE_OPENERS,
    ALL_SOFT_PERIOD_ABBREVIATIONS,
    ALL_TITLE_PERIOD_ABBREVIATIONS,
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
    FOLLOWING_LETTERED_LIST_ITEM_PATTERN,
    FOLLOWING_LIST_ITEM_PATTERN,
    HOOK_EVENT_NAME,
    INLINE_CODE_SPAN_PATTERN,
    MAXIMUM_MULTI_PART_ABBREVIATION_HEAD_LENGTH,
    MAXIMUM_SENTENCES_PER_OPTION_DESCRIPTION,
    MAXIMUM_SENTENCES_PER_QUESTION,
    MAXIMUM_WORDS_PER_SENTENCE,
    MINIMUM_ARROW_TOKENS_FOR_CHAIN,
    MINIMUM_CONTEXT_PREFIX_CHARACTER_COUNT,
    NEWLINE_JOIN_SEPARATOR,
    PROCESS_NARRATION_OPENER_PATTERN,
    STACKED_HYPHEN_COMPOUND_PATTERN,
    TOKEN_BEFORE_TERMINATOR_PATTERN,
    TOOL_NAME,
    USER_FACING_NOTICE,
    VERSION_INTERNAL_PERIOD_LOOKBEHIND_CHARACTER_COUNT,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def _is_inline_query_question_mark(text: str, question_mark_index: int) -> bool:
    """Return whether ``?`` is a URL/query/status marker, not the user ask.

    ::

        inline: path?x=1   path?X=1   status=?
        ask:    Which path?
        ask:    Pick one?The gate failed. Which fix?
        ask:    Which path?see the gate. How proceed?
    """
    if question_mark_index + 1 >= len(text):
        return False
    next_character = text[question_mark_index + 1]
    previous_character = text[question_mark_index - 1] if question_mark_index > 0 else ""
    # status=? / flag=? with no following alnum still is a query marker.
    if previous_character in "=&":
        return True
    if next_character in "=&_":
        return True
    if not next_character.isalnum():
        return False
    first_token = (
        text[question_mark_index + 1 :].split(maxsplit=1)[0]
        if text[question_mark_index + 1 :].split()
        else ""
    )
    # Real query strings carry assignment/join operators in the first token.
    if "=" in first_token or "&" in first_token:
        return True
    # path?x without a value is rare; glued prose is the common fail-open case.
    if previous_character.isalpha() or previous_character.isdigit():
        return False
    return True


def _first_top_level_question_mark_index(text: str) -> int:
    """Return the first outer ask ``?``, skipping nests, code spans, and query marks."""
    parenthesis_depth = 0
    bracket_depth = 0
    brace_depth = 0
    is_inside_inline_code = False
    for each_index, each_character in enumerate(text):
        if each_character == "`":
            is_inside_inline_code = not is_inside_inline_code
            continue
        if is_inside_inline_code:
            continue
        if each_character == "(":
            parenthesis_depth += 1
        elif each_character == ")":
            if parenthesis_depth > 0:
                parenthesis_depth -= 1
        elif each_character == "[":
            bracket_depth += 1
        elif each_character == "]":
            if bracket_depth > 0:
                bracket_depth -= 1
        elif each_character == "{":
            brace_depth += 1
        elif each_character == "}":
            if brace_depth > 0:
                brace_depth -= 1
        elif each_character == "?":
            if parenthesis_depth or bracket_depth or brace_depth:
                continue
            if _is_inline_query_question_mark(text, each_index):
                continue
            return each_index
    return -1


def _token_before_index(text: str, terminator_index: int) -> str:
    prefix = text[:terminator_index]
    token_match = TOKEN_BEFORE_TERMINATOR_PATTERN.search(prefix)
    if token_match is None:
        return ""
    return token_match.group(1)


def _next_alpha_word(text: str, start_index: int) -> str:
    rest_after = text[start_index:].lstrip()
    next_word = ""
    for each_character in rest_after:
        if each_character.isalpha():
            next_word += each_character
            continue
        break
    return next_word


def _following_sentence_start_character(text: str, start_index: int) -> str:
    """Return the character that would start the next sentence after a terminator."""
    index = start_index
    while index < len(text) and (text[index].isspace() or text[index] in ")]}\"'"):
        index += 1
    if index >= len(text):
        return ""
    return text[index]


def _is_numbered_list_marker(text: str, terminator_index: int, token: str) -> bool:
    """Return whether ``token.`` is a list marker (``1. The gate``), not ``3.12.`` / ``found 12.``."""
    if not token.isdigit():
        return False
    next_word = _next_alpha_word(text, terminator_index + 1)
    rest_after_marker = text[terminator_index + 1 :]
    # "47. Which" is a fact end; "1. Should … 2. …" stays a list.
    if next_word.lower() in ALL_BROAD_QUESTION_SENTENCE_OPENERS:
        if FOLLOWING_LIST_ITEM_PATTERN.search(rest_after_marker):
            return True
        return False
    segment_before_number = text[: terminator_index - len(token)].rstrip()
    if segment_before_number == "":
        return bool(next_word and next_word[0].isupper())
    if segment_before_number[-1] not in ".!?:":
        return False
    # Version tails: "3.12." — the period before this digit token is digit-adjacent.
    lookbehind_count = VERSION_INTERNAL_PERIOD_LOOKBEHIND_CHARACTER_COUNT
    if (
        segment_before_number[-1] == "."
        and len(segment_before_number) >= lookbehind_count
        and segment_before_number[-lookbehind_count].isdigit()
    ):
        return False
    # Colon labels ("Final score: 12. Which") are facts; list items continue
    # with a capital word or another numbered item later.
    if segment_before_number[-1] == ":":
        if not next_word or not next_word[0].isupper():
            return False
        rest_after_marker = text[terminator_index + 1 :]
        if FOLLOWING_LIST_ITEM_PATTERN.search(rest_after_marker):
            return True
        if next_word.lower() in ALL_BROAD_QUESTION_SENTENCE_OPENERS:
            return False
        return True
    return bool(next_word and next_word[0].isupper())


def _is_abbreviation_terminator(text: str, terminator_index: int) -> bool:
    if text[terminator_index] != ".":
        return False
    token = _token_before_index(text, terminator_index)
    if not token:
        return False
    # Numbered markers: "1. The gate" is not a sentence end at "1.".
    # A fact that ends on a number ("found 12. Which") still is.
    if _is_numbered_list_marker(text, terminator_index, token):
        return True
    next_word = _next_alpha_word(text, terminator_index + 1)
    # Single-letter tokens in multi-part abbrevs ("U.S." / "e.g." / "Ph.D.") are
    # not ends unless a real ask/sentence opener follows ("U.S. Which").
    if len(token) == 1 and token.isalpha():
        character_before_token_index = terminator_index - len(token) - 1
        is_multipart_tail = (
            character_before_token_index >= 0
            and text[character_before_token_index] == "."
        )
        if is_multipart_tail:
            # "U.S. Which" ends; "e.g. which is common" stays mid-phrase.
            return not (
                next_word
                and next_word[0].isupper()
                and next_word.lower() in ALL_QUESTION_SENTENCE_OPENERS
            )
        # Lettered list markers: "A. The gate..." / "A. Should … B. …" at BOL or after end.
        segment_before_letter = text[: terminator_index - len(token)].rstrip()
        if (
            token.isupper()
            and (segment_before_letter == "" or segment_before_letter[-1] in ".!?:")
            and next_word
            and next_word[0].isupper()
        ):
            rest_after_letter = text[terminator_index + 1 :]
            if next_word.lower() not in ALL_QUESTION_SENTENCE_OPENERS:
                return True
            if FOLLOWING_LETTERED_LIST_ITEM_PATTERN.search(rest_after_letter):
                return True
        following_start = _following_sentence_start_character(text, terminator_index + 1)
        if following_start == "" or following_start.islower():
            return True
        if len(next_word) == 1 and next_word.upper() != "I":
            return True
        return False
    # Multi-letter head of a multi-part abbrev (``Ph.D.``) — capital head +
    # single capital letter that is not the pronoun I.
    if (
        token.isalpha()
        and token[0].isupper()
        and len(token) <= MAXIMUM_MULTI_PART_ABBREVIATION_HEAD_LENGTH
        and len(next_word) == 1
        and next_word.isupper()
        and next_word.upper() != "I"
    ):
        return True
    lowered_token = token.lower()
    if lowered_token in ALL_TITLE_PERIOD_ABBREVIATIONS:
        # "Jr. Which" is a real end; "Dr. Smith" stays mid-name.
        return next_word.lower() not in ALL_QUESTION_SENTENCE_OPENERS
    if lowered_token in ALL_SOFT_PERIOD_ABBREVIATIONS:
        following = _following_sentence_start_character(text, terminator_index + 1)
        # "etc. How" is a real end; "etc. more" stays mid-phrase.
        return not (following == "" or following.isupper() or following in "\"'(")
    return False


def _is_inside_inline_code(text: str, index: int) -> bool:
    """Return whether index sits inside an odd number of backticks before it."""
    return text[:index].count("`") % 2 == 1


def _is_sentence_boundary(text: str, terminator_index: int) -> bool:
    """Return whether terminator_index is a real sentence end inside text."""
    if terminator_index < 0 or terminator_index >= len(text):
        return False
    if _is_inside_inline_code(text, terminator_index):
        return False
    terminator = text[terminator_index]
    if terminator not in ".!?":
        return False
    if terminator == "?" and _is_inline_query_question_mark(text, terminator_index):
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
    # Dotted suffixes like file.1 are not sentence ends (need space before digits).
    immediate_next = (
        text[terminator_index + 1] if terminator_index + 1 < len(text) else ""
    )
    if immediate_next.isdigit():
        return False
    following = _following_sentence_start_character(text, terminator_index + 1)
    if following == "":
        return True
    if following.isdigit():
        return True
    return following.isupper() or following in "\"'("


def _iter_statement_separator_ends(prefix: str) -> list[int]:
    """Return end indices of statement separators inside prefix (after closers/spaces)."""
    all_ends: list[int] = []
    for each_match in CLAUSE_SEPARATOR_PATTERN.finditer(prefix):
        if _is_inside_inline_code(prefix, each_match.start()):
            continue
        all_ends.append(each_match.end())
    for each_index, each_character in enumerate(prefix):
        if each_character not in ".!?":
            continue
        if not _is_sentence_boundary(prefix, each_index):
            continue
        cursor = each_index + 1
        while cursor < len(prefix) and prefix[cursor] in "\"')]}":
            cursor += 1
        while cursor < len(prefix) and prefix[cursor].isspace():
            cursor += 1
        all_ends.append(cursor)
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
    first_question_mark_index = _first_top_level_question_mark_index(stripped_text)
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
            closer_characters = "\"')]} "
            while (
                following_start < len(stripped_text)
                and stripped_text[following_start] in closer_characters
                and not stripped_text[following_start].isspace()
            ):
                following_start += 1
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
    closer_only = set("\"')]} ")
    if trailing and not all(each_character in closer_only for each_character in trailing):
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


def _strip_inline_code_spans(prose_text: str) -> str:
    return INLINE_CODE_SPAN_PATTERN.sub("", prose_text)


def _collect_plain_brief_findings(prose_text: str, all_findings: list[str]) -> None:
    # Exact identifiers in backticks stay out of structure scans.
    structure_text = _strip_inline_code_spans(prose_text)
    stripped_text = structure_text.strip()
    if PROCESS_NARRATION_OPENER_PATTERN.search(stripped_text) is not None:
        _record_finding(all_findings, FINDING_PROCESS_NARRATION)
    if len(ARROW_TOKEN_PATTERN.findall(structure_text)) >= MINIMUM_ARROW_TOKENS_FOR_CHAIN:
        _record_finding(all_findings, FINDING_ARROW_CHAIN)
    if STACKED_HYPHEN_COMPOUND_PATTERN.search(structure_text) is not None:
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
