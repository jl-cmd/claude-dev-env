"""Behavior tests for state_description_blocker configuration constants."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from blocking.state_description_blocker import _extract_comment_lines
from hooks_constants.state_description_blocker_constants import (
    ALL_BLOCK_COMMENT_EXTENSIONS,
    ALL_COMMENT_TRANSITION_PATTERNS,
    ALL_HASH_ONLY_EXTENSIONS,
    ALL_MARKDOWN_EXTENSIONS,
    BLOCK_COMMENT_CLOSE_MARKER,
    BLOCK_COMMENT_OPEN_MARKER,
    DOUBLE_QUOTE_BODY_GROUP,
    SINGLE_QUOTE_BODY_GROUP,
    TRIPLE_QUOTED_BLOCK_PATTERN,
)


def test_transition_patterns_match_their_own_phrase() -> None:
    all_phrases = [
        "instead of",
        "previously",
        "was previously",
        "used to",
        "no longer",
        "switched to",
    ]
    for each_phrase in all_phrases:
        sentence = f"The field is {each_phrase} required."
        assert any(
            each_pattern.search(sentence) for each_pattern in ALL_COMMENT_TRANSITION_PATTERNS
        ), each_phrase


def test_transition_patterns_do_not_match_unrelated_prose() -> None:
    sentence = "The path selects the scan strategy for the file."
    assert not any(
        each_pattern.search(sentence) for each_pattern in ALL_COMMENT_TRANSITION_PATTERNS
    )


def test_block_comment_markers_close_a_single_line_block_comment() -> None:
    text = f"{BLOCK_COMMENT_OPEN_MARKER} note {BLOCK_COMMENT_CLOSE_MARKER}\ncode();"
    all_comment_lines = _extract_comment_lines(text, ".js")
    assert all_comment_lines == [
        (1, f"{BLOCK_COMMENT_OPEN_MARKER} note {BLOCK_COMMENT_CLOSE_MARKER}")
    ]


def test_block_comment_markers_carry_an_unclosed_comment_to_the_next_line() -> None:
    text = f"{BLOCK_COMMENT_OPEN_MARKER} still open\nclosed here {BLOCK_COMMENT_CLOSE_MARKER}"
    all_comment_lines = _extract_comment_lines(text, ".js")
    assert all_comment_lines == [
        (1, f"{BLOCK_COMMENT_OPEN_MARKER} still open"),
        (2, f"closed here {BLOCK_COMMENT_CLOSE_MARKER}"),
    ]


def test_double_and_single_quote_body_groups_index_the_matching_quote_style() -> None:
    double_quoted_match = TRIPLE_QUOTED_BLOCK_PATTERN.search('"""double body"""')
    assert double_quoted_match is not None
    assert double_quoted_match.group(DOUBLE_QUOTE_BODY_GROUP) == "double body"
    assert double_quoted_match.group(SINGLE_QUOTE_BODY_GROUP) is None

    single_quoted_match = TRIPLE_QUOTED_BLOCK_PATTERN.search("'''single body'''")
    assert single_quoted_match is not None
    assert single_quoted_match.group(SINGLE_QUOTE_BODY_GROUP) == "single body"
    assert single_quoted_match.group(DOUBLE_QUOTE_BODY_GROUP) is None


def test_extension_sets_are_disjoint_from_markdown_extensions() -> None:
    assert not (ALL_HASH_ONLY_EXTENSIONS & ALL_MARKDOWN_EXTENSIONS)
    assert not (ALL_BLOCK_COMMENT_EXTENSIONS & ALL_MARKDOWN_EXTENSIONS)


def test_python_is_hash_only_and_never_block_comment() -> None:
    assert ".py" in ALL_HASH_ONLY_EXTENSIONS
    assert ".py" not in ALL_BLOCK_COMMENT_EXTENSIONS
