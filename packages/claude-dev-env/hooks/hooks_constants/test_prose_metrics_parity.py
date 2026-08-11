"""Parity checks across the duplicated prose-metric copies.

``plain_language_blocker_constants`` and ``eli11_reply_enforcer_constants``
each carry their own copy of the metrics that read a reply's prose, so a
tuning landed in one copy alone drifts the two gates apart. These checks fail
loud on that drift::

    COUNTABLE_WORD_PATTERN      ok:   byte-equal across both copies
    table-row pattern           ok:   byte-equal across both copies
    "- Run the migration"       ok:   both copies read a list marker
    "1.5% of hosts still fail." ok:   neither copy reads a list marker
    "**1.** Run the migration"  flag: the eli11 copy alone reads a marker

The list-marker copies hold two different shapes — one combined regex against
a bullet/numbered split — so they are pinned by the lines they agree on plus
the one line they read differently.

Row 2 of ``~/.claude/orchestrator-runs/falsify-first/parked-items.md`` carries
the shared home that retires these copies.
"""

import pathlib
import re
import sys

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.eli11_reply_enforcer_constants import (
    BULLET_LINE_PATTERN,
    NUMBERED_STEP_PATTERN,
    TABLE_ROW_PATTERN,
)
from hooks_constants.eli11_reply_enforcer_constants import (
    COUNTABLE_WORD_PATTERN as ELI11_COUNTABLE_WORD_PATTERN,
)
from hooks_constants.ask_user_question_shape import (
    COUNTABLE_WORD_PATTERN as SHAPE_COUNTABLE_WORD_PATTERN,
)
from hooks_constants.plain_language_blocker_constants import ALL_CHAT_DETAIL_MARKERS
from hooks_constants.plain_language_blocker_constants import (
    COUNTABLE_WORD_PATTERN as PLAIN_LANGUAGE_COUNTABLE_WORD_PATTERN,
)

_TABLE_ROW_MARKER_LABEL = "a table row"
_LIST_MARKER_LABEL = "a bullet or numbered list marker"
_BOLD_NUMBERED_STEP_LINE = "**1.** Run the migration"

_ALL_SHARED_LIST_MARKER_LINES = (
    "- Run the migration",
    "* Run the migration",
    "+ Run the migration",
    "1. Run the migration",
    "2) Run the migration",
    "   - Run the migration",
    "  1. Run the migration",
)

_ALL_NON_LIST_MARKER_LINES = (
    "Run the migration",
    "1.5% of hosts still fail.",
    "|table|row|",
    "-no space after the dash",
)


def _chat_detail_marker_named(marker_label: str) -> re.Pattern[str]:
    """Return the plain-language chat-detail pattern carrying one label.

    Args:
        marker_label: The label the chat-detail marker table gives a pattern.

    Returns:
        The compiled pattern registered under that label.
    """
    for each_pattern, each_label in ALL_CHAT_DETAIL_MARKERS:
        if each_label == marker_label:
            return each_pattern
    raise AssertionError(f"no chat-detail marker labeled {marker_label!r}")


def _eli11_copy_reads_a_list_marker(reply_line: str) -> bool:
    """Report whether the eli11 bullet/numbered split reads a list marker.

    Args:
        reply_line: One line of reply text.

    Returns:
        True when either half of the split matches the line.
    """
    if BULLET_LINE_PATTERN.search(reply_line):
        return True
    return bool(NUMBERED_STEP_PATTERN.search(reply_line))


def test_countable_word_pattern_copies_stay_byte_equal() -> None:
    assert (
        PLAIN_LANGUAGE_COUNTABLE_WORD_PATTERN.pattern
        == ELI11_COUNTABLE_WORD_PATTERN.pattern
    )
    assert (
        PLAIN_LANGUAGE_COUNTABLE_WORD_PATTERN.flags
        == ELI11_COUNTABLE_WORD_PATTERN.flags
    )


def test_shape_analyzer_binds_the_plain_language_countable_word_pattern() -> None:
    """The pure shape analyzer reuses the shared pattern object, not a private copy."""
    assert SHAPE_COUNTABLE_WORD_PATTERN is PLAIN_LANGUAGE_COUNTABLE_WORD_PATTERN


def test_table_row_pattern_copies_stay_byte_equal() -> None:
    plain_language_table_row = _chat_detail_marker_named(_TABLE_ROW_MARKER_LABEL)
    assert plain_language_table_row.pattern == TABLE_ROW_PATTERN.pattern
    assert plain_language_table_row.flags == TABLE_ROW_PATTERN.flags


def test_list_marker_copies_agree_on_every_shared_line() -> None:
    combined_marker = _chat_detail_marker_named(_LIST_MARKER_LABEL)
    for each_line in _ALL_SHARED_LIST_MARKER_LINES:
        assert combined_marker.search(each_line)
        assert _eli11_copy_reads_a_list_marker(each_line)
    for each_line in _ALL_NON_LIST_MARKER_LINES:
        assert not combined_marker.search(each_line)
        assert not _eli11_copy_reads_a_list_marker(each_line)


def test_bold_numbered_step_reads_as_a_list_marker_in_the_eli11_copy_alone() -> None:
    combined_marker = _chat_detail_marker_named(_LIST_MARKER_LABEL)
    assert not combined_marker.search(_BOLD_NUMBERED_STEP_LINE)
    assert _eli11_copy_reads_a_list_marker(_BOLD_NUMBERED_STEP_LINE)
