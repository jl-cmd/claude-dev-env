"""Constants for AskUserQuestion field-shape validation."""

from __future__ import annotations

import re

__all__ = [
    "ALL_CHAT_DETAIL_MARKERS",
    "ALL_LINE_ENDING_REPLACEMENTS",
    "ASK_USER_QUESTION_TOOL_NAME",
    "COUNTABLE_WORD_PATTERN",
    "INLINE_CODE_PLACEHOLDER",
    "INLINE_CODE_SPAN_PATTERN",
    "LEAN_QUESTION_BLOCK_GUIDANCE",
    "LEAN_QUESTION_BLOCK_PREFIX",
    "LEAN_QUESTION_VIOLATION_SEPARATOR",
    "MAXIMUM_OPTION_DESCRIPTION_SENTENCE_COUNT",
    "MAXIMUM_OPTION_DESCRIPTION_WORD_COUNT",
    "MAXIMUM_QUESTION_SENTENCE_COUNT",
    "MAXIMUM_QUESTION_WORD_COUNT",
    "OPTION_DESCRIPTION_SURFACE_NAME",
    "QUESTION_SURFACE_NAME",
    "SENTENCE_BOUNDARY_PATTERN",
    "USER_FACING_LEAN_QUESTION_NOTICE",
]

ASK_USER_QUESTION_TOOL_NAME: str = "AskUserQuestion"

ALL_CHAT_DETAIL_MARKERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^[ \t]*```", re.MULTILINE), "a fenced code block"),
    (re.compile(r"^[ \t]*#{1,6}[ \t]+\S", re.MULTILINE), "a heading"),
    (re.compile(r"^[ \t]*\|.*\|[ \t]*$", re.MULTILINE), "a table row"),
    (
        re.compile(r"^[ \t]*(?:[-*+][ \t]+|\d{1,2}[.)][ \t]+)\S", re.MULTILINE),
        "a bullet or numbered list marker",
    ),
    (re.compile(r"\n[ \t]*\n"), "more than one paragraph"),
)

INLINE_CODE_SPAN_PATTERN: re.Pattern[str] = re.compile(r"`[^`\n]+`")
INLINE_CODE_PLACEHOLDER: str = "code"

ALL_LINE_ENDING_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("\r\n", "\n"),
    ("\r", "\n"),
)

SENTENCE_BOUNDARY_PATTERN: re.Pattern[str] = re.compile(
    r"[.!?]+(?=\s+[A-Z]|\s*$)"
)
COUNTABLE_WORD_PATTERN: re.Pattern[str] = re.compile(r"\S*[A-Za-z0-9]\S*")

MAXIMUM_QUESTION_SENTENCE_COUNT: int = 2
MAXIMUM_QUESTION_WORD_COUNT: int = 40
MAXIMUM_OPTION_DESCRIPTION_SENTENCE_COUNT: int = 1
MAXIMUM_OPTION_DESCRIPTION_WORD_COUNT: int = 15

QUESTION_SURFACE_NAME: str = "the question"
OPTION_DESCRIPTION_SURFACE_NAME: str = "an option description"

LEAN_QUESTION_BLOCK_PREFIX: str = (
    "BLOCKED: [LEAN_QUESTION] Question block carries chat detail -- "
)
LEAN_QUESTION_VIOLATION_SEPARATOR: str = "; "
LEAN_QUESTION_BLOCK_GUIDANCE: str = (
    "AskUserQuestion renders as one plain text block. Print the plan, the counts, "
    "and the tradeoffs in chat text before the call, keep the question block to a "
    "lean question and short options, and reach for an inline visualizer tool when "
    "a choice needs formatting."
)
USER_FACING_LEAN_QUESTION_NOTICE: str = (
    "Question-block check: move the detail into chat and ask a short question."
)
