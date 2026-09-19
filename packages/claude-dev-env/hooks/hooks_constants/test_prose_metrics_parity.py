"""Contract tests for the retained AskUserQuestion shape capability."""

from __future__ import annotations

import pathlib
import re
import sys

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.ask_user_question_shape_constants import (  # noqa: E402
    ALL_CHAT_DETAIL_MARKERS,
)


def _marker_pattern(marker_label: str) -> re.Pattern[str]:
    """Return the pattern registered under one shape-marker label."""
    for each_pattern, each_label in ALL_CHAT_DETAIL_MARKERS:
        if each_label == marker_label:
            return each_pattern
    raise AssertionError(f"missing shape marker: {marker_label}")


def test_shape_marker_table_reads_shared_layout_markers() -> None:
    table_pattern = _marker_pattern("a table row")
    list_pattern = _marker_pattern("a bullet or numbered list marker")

    assert table_pattern.search("| gate | row |")
    assert list_pattern.search("- Run the migration")
    assert list_pattern.search("1. Run the migration")
    assert not list_pattern.search("1.5% of hosts still fail.")

