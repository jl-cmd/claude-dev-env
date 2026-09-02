"""Tests for multi_edit_reconstruction.py."""

from __future__ import annotations

import pathlib
import sys

try:
    _HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_HOOKS_ROOT) not in sys.path:
        sys.path.insert(0, str(_HOOKS_ROOT))

    from hooks_constants.multi_edit_reconstruction import (
        apply_edits,
        edits_for_tool,
        joined_new_strings,
    )
except ImportError as import_error:
    raise ImportError(
        "test_multi_edit_reconstruction: cannot import its sibling modules; "
        "ensure the hooks directory is importable."
    ) from import_error


def test_apply_edits_replaces_each_old_string_in_list_order() -> None:
    """Two edits land in order, each replacing its own first occurrence."""
    all_edits = [
        {"old_string": "alpha", "new_string": "beta"},
        {"old_string": "gamma", "new_string": "delta"},
    ]
    assert apply_edits("alpha gamma", all_edits) == "beta delta"


def test_edits_for_tool_wraps_an_edit_payload_in_a_single_element_list() -> None:
    """An Edit payload is its own only edit."""
    edit_payload = {"old_string": "a", "new_string": "b"}
    assert edits_for_tool("Edit", edit_payload) == [edit_payload]


def test_apply_edits_replaces_every_occurrence_when_replace_all_is_set() -> None:
    """A replace_all edit rewrites every occurrence, the way MultiEdit does.

    The gates that read this reconstruction judge the file the write would
    leave on disk. When an edit carries replace_all, MultiEdit rewrites all
    occurrences, so a reconstruction that rewrites only the first one hands
    every gate a file that never existed.
    """
    all_edits = [{"old_string": "old", "new_string": "new", "replace_all": True}]
    assert apply_edits("old old old", all_edits) == "new new new"


def test_apply_edits_replaces_only_the_first_occurrence_without_replace_all() -> None:
    """An edit with no replace_all flag rewrites one occurrence."""
    all_edits = [{"old_string": "old", "new_string": "new"}]
    assert apply_edits("old old old", all_edits) == "new old old"


def test_apply_edits_treats_a_false_replace_all_as_a_single_replacement() -> None:
    """An explicit replace_all of False rewrites one occurrence."""
    all_edits = [{"old_string": "old", "new_string": "new", "replace_all": False}]
    assert apply_edits("old old old", all_edits) == "new old old"


def test_apply_edits_mixes_replace_all_and_single_edits_in_one_list() -> None:
    """Each edit in a list honors its own flag, not the list's first one."""
    all_edits = [
        {"old_string": "a", "new_string": "A", "replace_all": True},
        {"old_string": "b", "new_string": "B"},
    ]
    assert apply_edits("a b a b", all_edits) == "A B A b"


def test_joined_new_strings_joins_every_new_string_on_a_newline() -> None:
    """Each edit's introduced text reaches the scanner as its own line."""
    tool_input = {
        "edits": [
            {"old_string": "x", "new_string": "import os"},
            {"old_string": "y", "new_string": "shutil.rmtree(p)"},
        ]
    }
    assert joined_new_strings(tool_input) == "import os\nshutil.rmtree(p)"


def test_joined_new_strings_separator_keeps_adjacent_edits_apart() -> None:
    """A phrase spanning the seam belongs to neither edit, so the join breaks it."""
    tool_input = {
        "edits": [
            {"old_string": "x", "new_string": "currently"},
            {"old_string": "y", "new_string": "holds"},
        ]
    }
    assert "currentlyholds" not in joined_new_strings(tool_input)


def test_joined_new_strings_skips_edits_whose_new_string_is_not_a_string() -> None:
    """A malformed edit contributes nothing rather than raising."""
    tool_input = {"edits": [{"new_string": None}, {"new_string": "kept"}]}
    assert joined_new_strings(tool_input) == "kept"


def test_joined_new_strings_returns_empty_text_for_a_payload_with_no_edits() -> None:
    """A payload carrying no edit list scans as empty text."""
    assert joined_new_strings({"file_path": "a.py"}) == ""
