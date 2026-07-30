"""Pure AskUserQuestion payload-shape analysis.

Maps an AskUserQuestion tool input to lean-block violations without hook I/O,
deny payloads, or environment state::

    analyze_ask_user_question_shape({"questions": [...]})
        ok:   a lean question and short options -> empty violations
        flag: a bullet list under the question  -> named violation texts

Callers that need a deny reason compose with the shared lean-block message
constants; this module only grades shape.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hooks_constants.plain_language_blocker_constants import (
    ALL_CHAT_DETAIL_MARKERS,
    ALL_LINE_ENDING_REPLACEMENTS,
    COUNTABLE_WORD_PATTERN,
    INLINE_CODE_PLACEHOLDER,
    INLINE_CODE_SPAN_PATTERN,
    MAXIMUM_OPTION_DESCRIPTION_SENTENCE_COUNT,
    MAXIMUM_OPTION_DESCRIPTION_WORD_COUNT,
    MAXIMUM_QUESTION_SENTENCE_COUNT,
    MAXIMUM_QUESTION_WORD_COUNT,
    OPTION_DESCRIPTION_SURFACE_NAME,
    QUESTION_SURFACE_NAME,
    SENTENCE_BOUNDARY_PATTERN,
)

__all__ = [
    "AskUserQuestionShapeResult",
    "analyze_ask_user_question_shape",
    "count_prose_sentences",
    "count_prose_words",
    "find_chat_detail_markers",
    "find_lean_block_violations",
    "find_question_block_violations",
    "mask_inline_code",
    "normalize_line_endings",
    "violations_for_one_question",
]


@dataclass(frozen=True)
class AskUserQuestionShapeResult:
    """Shape-grade for one AskUserQuestion tool input.

    Attributes:
        all_violations: One violation text per broken lean-block rule, in
            first-seen order, empty when the whole question block is lean.
    """

    all_violations: tuple[str, ...]

    @property
    def is_lean(self) -> bool:
        """True when the payload carries no lean-block violations."""
        return not self.all_violations


def normalize_line_endings(prose_text: str) -> str:
    """Return the prose with every line ending spelled as a bare line feed.

    ::

        in:  "Which gate?\\r\\n\\r\\nThe write gate reads it."
        out: "Which gate?\\n\\nThe write gate reads it."

    Args:
        prose_text: One question text or one option description.

    Returns:
        The prose with carriage returns folded into line feeds.
    """
    normalized_text = prose_text
    for each_line_ending, each_replacement in ALL_LINE_ENDING_REPLACEMENTS:
        normalized_text = normalized_text.replace(each_line_ending, each_replacement)
    return normalized_text


def mask_inline_code(prose_text: str) -> str:
    """Return the prose with each inline code span collapsed to a single word.

    ::

        in:  "Does `git diff --cached` list it?"
        out: "Does code list it?"

    Args:
        prose_text: One question text or one option description.

    Returns:
        The prose with every single-line inline code span replaced.
    """
    return INLINE_CODE_SPAN_PATTERN.sub(INLINE_CODE_PLACEHOLDER, prose_text)


def count_prose_sentences(prose_text: str) -> int:
    """Return how many sentences one piece of question-block prose carries.

    ::

        in:  "Which gate runs first? Both read the same lines."
        out: 2

    Args:
        prose_text: One question text or one option description.

    Returns:
        The count of sentence closings the prose carries.
    """
    return len(SENTENCE_BOUNDARY_PATTERN.findall(prose_text))


def count_prose_words(prose_text: str) -> int:
    """Return how many reader-visible words one piece of prose carries.

    Args:
        prose_text: One question text or one option description.

    Returns:
        The count of whitespace-separated tokens carrying a letter or digit.
    """
    return len(COUNTABLE_WORD_PATTERN.findall(prose_text))


def find_chat_detail_markers(prose_text: str) -> list[str]:
    """Return the name of each chat-detail marker the prose carries.

    ::

        ok:   "Which gate should run first?"        -> []
        flag: "Which gate?\\n- write\\n- commit"      -> ["a bullet or numbered
              list marker"]

    Args:
        prose_text: One question text or one option description.

    Returns:
        One marker name per marker found, in the order the markers are tried.
    """
    return [
        each_marker_name
        for each_pattern, each_marker_name in ALL_CHAT_DETAIL_MARKERS
        if each_pattern.search(prose_text)
    ]


def find_lean_block_violations(
    prose_text: str,
    surface_name: str,
    maximum_sentence_count: int,
    maximum_word_count: int,
) -> list[str]:
    """Return every lean-block rule one piece of question-block prose breaks.

    Args:
        prose_text: One question text or one option description.
        surface_name: How the violation text names this piece of prose.
        maximum_sentence_count: The sentence cap this piece answers to.
        maximum_word_count: The word cap this piece answers to.

    Returns:
        One violation text per broken rule, empty when the prose is lean.
    """
    normalized_text = normalize_line_endings(prose_text)
    masked_text = mask_inline_code(normalized_text)
    all_violations = [
        f"{surface_name} carries {each_marker_name}"
        for each_marker_name in find_chat_detail_markers(normalized_text)
    ]
    sentence_count = count_prose_sentences(masked_text)
    if sentence_count > maximum_sentence_count:
        all_violations.append(
            f"{surface_name} runs {sentence_count} sentences, over the "
            f"{maximum_sentence_count}-sentence cap"
        )
    word_count = count_prose_words(masked_text)
    if word_count > maximum_word_count:
        all_violations.append(
            f"{surface_name} runs {word_count} words, over the "
            f"{maximum_word_count}-word cap"
        )
    return all_violations


def violations_for_one_question(question_by_key: Mapping[str, object]) -> list[str]:
    """Return the lean-block violations one question entry carries.

    Args:
        question_by_key: One entry of the AskUserQuestion questions list.

    Returns:
        One violation text per broken rule across the question text and every
        option description the entry carries.
    """
    all_violations: list[str] = []
    question_text = question_by_key.get("question", "")
    if isinstance(question_text, str):
        all_violations.extend(
            find_lean_block_violations(
                question_text,
                QUESTION_SURFACE_NAME,
                MAXIMUM_QUESTION_SENTENCE_COUNT,
                MAXIMUM_QUESTION_WORD_COUNT,
            )
        )
    all_options = question_by_key.get("options", [])
    if not isinstance(all_options, Sequence) or isinstance(all_options, (str, bytes)):
        return all_violations
    for each_option in all_options:
        if not isinstance(each_option, Mapping):
            continue
        option_description = each_option.get("description", "")
        if not isinstance(option_description, str):
            continue
        all_violations.extend(
            find_lean_block_violations(
                option_description,
                OPTION_DESCRIPTION_SURFACE_NAME,
                MAXIMUM_OPTION_DESCRIPTION_SENTENCE_COUNT,
                MAXIMUM_OPTION_DESCRIPTION_WORD_COUNT,
            )
        )
    return all_violations


def find_question_block_violations(payload_by_key: Mapping[str, object]) -> list[str]:
    """Return every lean-block violation an AskUserQuestion payload carries.

    ::

        ok:   "Which gate should run first?" + "Runs on every write." -> []
        flag: a question with a three-bullet plan under it
              -> ["the question carries a bullet or numbered list marker"]

    Each violation text appears once, so two options breaking the same cap read
    as one line.

    Args:
        payload_by_key: The AskUserQuestion tool input carrying the questions list.

    Returns:
        One violation text per broken rule, in first-seen order, empty when the
        whole question block is lean.
    """
    all_questions = payload_by_key.get("questions", [])
    if not isinstance(all_questions, Sequence) or isinstance(all_questions, (str, bytes)):
        return []
    all_violations: list[str] = []
    for each_question in all_questions:
        if isinstance(each_question, Mapping):
            all_violations.extend(violations_for_one_question(each_question))
    return list(dict.fromkeys(all_violations))


def analyze_ask_user_question_shape(
    payload_by_key: Mapping[str, object],
) -> AskUserQuestionShapeResult:
    """Grade an AskUserQuestion tool input for lean-block shape only.

    ::

        analyze_ask_user_question_shape({"questions": [
            {"question": "Which gate?", "options": [{"description": "Runs on write."}]}
        ]}).is_lean
            True

    Args:
        payload_by_key: The AskUserQuestion tool input carrying the questions list.

    Returns:
        A frozen result holding the ordered, de-duplicated violation texts.
    """
    return AskUserQuestionShapeResult(
        all_violations=tuple(find_question_block_violations(payload_by_key))
    )
