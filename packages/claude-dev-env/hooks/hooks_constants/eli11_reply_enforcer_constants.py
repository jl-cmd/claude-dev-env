"""Tunables for the eli11_reply_enforcer Stop hook.

::

    NUMBERED_STEP_PATTERN
        ok:   "1. Run the script"      flag: "1.5% of hosts still fail."
    ALL_IMPERATIVE_OBJECT_LEAD_WORDS
        ok:   "Run the migration"      flag: "Run time stays under a second"

Holds the reply-shape thresholds the `eli11-replies` rule names, the compiled
patterns that read a reply's structure, the closed sets naming an instruction
verb and its object, and the notice the hook shows when it blocks.
"""

import re

__all__ = [
    "ACTION_FIRST_LEAD_LINE_COUNT",
    "ALL_IMPERATIVE_INSTRUCTION_VERBS",
    "ALL_IMPERATIVE_OBJECT_LEAD_WORDS",
    "ALPHABETIC_WORD_PATTERN",
    "BULLET_LINE_PATTERN",
    "COUNTABLE_WORD_PATTERN",
    "IMPERATIVE_OBJECT_TOKEN_PATTERN",
    "LINK_TARGET_PATTERN",
    "LIST_MARKER_PREFIX_PATTERN",
    "LONG_FORM_ESCAPE_PREFIX",
    "MARKDOWN_LEAD_MARKER_PATTERN",
    "MAXIMUM_BULLET_LINE_COUNT",
    "MAXIMUM_OVERPACKED_LINE_COUNT",
    "MAXIMUM_REPLY_WORD_COUNT",
    "MAXIMUM_WORDS_PER_LINE",
    "MINIMUM_ENFORCED_WORD_COUNT",
    "NUMBERED_STEP_PATTERN",
    "TABLE_ROW_PATTERN",
    "TARGET_BULLET_LINE_COUNT",
    "USER_FACING_ELI11_NOTICE",
    "VIOLATION_SEPARATOR",
]

MAXIMUM_REPLY_WORD_COUNT = 120
MINIMUM_ENFORCED_WORD_COUNT = 60
MAXIMUM_BULLET_LINE_COUNT = 6
TARGET_BULLET_LINE_COUNT = 3
ACTION_FIRST_LEAD_LINE_COUNT = 6
MAXIMUM_WORDS_PER_LINE = 20
MAXIMUM_OVERPACKED_LINE_COUNT = 2

LONG_FORM_ESCAPE_PREFIX = "long form:"
VIOLATION_SEPARATOR = "; "
USER_FACING_ELI11_NOTICE = "Agent wrote a long reply - rewriting it short..."

TABLE_ROW_PATTERN = re.compile(r"^[ \t]*\|.*\|[ \t]*$", re.MULTILINE)
LINK_TARGET_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
COUNTABLE_WORD_PATTERN = re.compile(r"\S*[A-Za-z0-9]\S*")
ALPHABETIC_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'’-]*")
BULLET_LINE_PATTERN = re.compile(r"^[ \t]*[-*+][ \t]+\S")
NUMBERED_STEP_PATTERN = re.compile(r"^[ \t]*(?:\*\*)?\d{1,2}[.)](?:\*\*)?[ \t]+\S")
LIST_MARKER_PREFIX_PATTERN = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+|(?:\*\*)?\d{1,2}[.)][ \t]*)?(?:\*\*)?"
)
MARKDOWN_LEAD_MARKER_PATTERN = re.compile(r"^(?:[ \t]*(?:>+|#{1,6}|\*\*|__|\*|_))+[ \t]*")

ALL_IMPERATIVE_INSTRUCTION_VERBS = (
    "click",
    "copy",
    "delete",
    "do",
    "download",
    "install",
    "merge",
    "open",
    "paste",
    "restart",
    "run",
    "save",
)

ALL_IMPERATIVE_OBJECT_LEAD_WORDS = (
    "a",
    "all",
    "an",
    "any",
    "both",
    "each",
    "every",
    "into",
    "it",
    "my",
    "our",
    "that",
    "the",
    "them",
    "these",
    "this",
    "those",
    "to",
    "your",
)

IMPERATIVE_OBJECT_TOKEN_PATTERN = re.compile(r"^\d|[`/\\]|\.[A-Za-z]{1,4}$")
