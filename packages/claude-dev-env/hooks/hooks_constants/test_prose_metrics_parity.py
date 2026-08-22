"""Contract tests for the retained AskUserQuestion shape capability."""

from __future__ import annotations

import pathlib
import re
import sys

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.ask_user_question_shape import (  # noqa: E402
    COUNTABLE_WORD_PATTERN as ANALYZER_COUNTABLE_WORD_PATTERN,
    find_chat_detail_markers,
)
from hooks_constants.ask_user_question_shape_constants import (  # noqa: E402
    ALL_CHAT_DETAIL_MARKERS,
    COUNTABLE_WORD_PATTERN,
)


def _marker_pattern(marker_label: str) -> re.Pattern[str]:
    """Return the pattern registered under one shape-marker label."""
    for each_pattern, each_label in ALL_CHAT_DETAIL_MARKERS:
        if each_label == marker_label:
            return each_pattern
    raise AssertionError(f"missing shape marker: {marker_label}")


def test_analyzer_uses_the_canonical_countable_word_pattern() -> None:
    assert ANALYZER_COUNTABLE_WORD_PATTERN is COUNTABLE_WORD_PATTERN


def test_shape_marker_table_reads_shared_layout_markers() -> None:
    table_pattern = _marker_pattern("a table row")
    list_pattern = _marker_pattern("a bullet or numbered list marker")

    assert table_pattern.search("| gate | row |")
    assert list_pattern.search("- Run the migration")
    assert list_pattern.search("1. Run the migration")
    assert not list_pattern.search("1.5% of hosts still fail.")


def test_analyzer_reports_each_layout_marker() -> None:
    marker_names = find_chat_detail_markers(
        "Question?\n- Split the file\n\n| gate | row |"
    )

    assert marker_names == [
        "a table row",
        "a bullet or numbered list marker",
        "more than one paragraph",
    ]
