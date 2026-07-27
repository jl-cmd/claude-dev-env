"""Tunables for the eli11_reply_enforcer Stop hook.

Holds the reply-shape thresholds the `eli11-replies` rule names, the compiled
patterns that find bullets, numbered steps, table rows, link targets, and
words in a reply, and the user-facing notice the hook emits when it blocks.
"""

import re

__all__ = [
    "ACTION_FIRST_LEAD_LINE_COUNT",
    "ALL_IMPERATIVE_INSTRUCTION_VERBS",
    "ALPHABETIC_WORD_PATTERN",
    "BULLET_LINE_PATTERN",
    "COUNTABLE_WORD_PATTERN",
    "LINK_TARGET_PATTERN",
    "LIST_MARKER_PREFIX_PATTERN",
    "LONG_FORM_ESCAPE_PREFIX",
    "MAXIMUM_BULLET_LINE_COUNT",
    "MAXIMUM_REPLY_WORD_COUNT",
    "MINIMUM_ENFORCED_WORD_COUNT",
    "NUMBERED_STEP_PATTERN",
    "TABLE_ROW_PATTERN",
    "TARGET_BULLET_LINE_COUNT",
    "USER_FACING_ELI11_NOTICE",
    "VIOLATION_SEPARATOR",
]

MAXIMUM_REPLY_WORD_COUNT = 220
MINIMUM_ENFORCED_WORD_COUNT = 80
MAXIMUM_BULLET_LINE_COUNT = 6
TARGET_BULLET_LINE_COUNT = 3
ACTION_FIRST_LEAD_LINE_COUNT = 6

LONG_FORM_ESCAPE_PREFIX = "long form:"
VIOLATION_SEPARATOR = "; "
USER_FACING_ELI11_NOTICE = "Agent wrote a long reply - rewriting it short..."

TABLE_ROW_PATTERN = re.compile(r"^[ \t]*\|.*\|[ \t]*$", re.MULTILINE)
LINK_TARGET_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
COUNTABLE_WORD_PATTERN = re.compile(r"\S*[A-Za-z0-9]\S*")
ALPHABETIC_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'’-]*")
BULLET_LINE_PATTERN = re.compile(r"^[ \t]*[-*+][ \t]+\S")
NUMBERED_STEP_PATTERN = re.compile(r"^[ \t]*(?:\*\*)?\d+[.)]")
LIST_MARKER_PREFIX_PATTERN = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+|(?:\*\*)?\d+[.)][ \t]*)?(?:\*\*)?"
)

ALL_IMPERATIVE_INSTRUCTION_VERBS = ("run", "click", "merge", "open")
