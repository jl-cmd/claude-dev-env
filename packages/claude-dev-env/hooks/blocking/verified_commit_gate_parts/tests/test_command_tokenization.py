"""Behavioral tests for the verified-commit gate's command tokenization."""

import re

from verified_commit_gate_parts.command_tokenization import (
    collapse_line_continuations,
    command_carries_trailing_marker,
    containing_quoted_span,
    git_word_match_gates,
    is_inside_quoted_region,
    quoted_spans,
    strip_token_quotes,
)

VERIFY_SKIP_MARKER = "# verify-skip"


def test_command_carries_trailing_marker_true_for_a_real_trailing_comment() -> None:
    command_text = f'git commit -m "wire up" {VERIFY_SKIP_MARKER}'
    assert command_carries_trailing_marker(command_text, VERIFY_SKIP_MARKER)


def test_command_carries_trailing_marker_false_when_marker_sits_inside_quotes() -> None:
    command_text = f'git commit -m "explain the {VERIFY_SKIP_MARKER} hatch"'
    assert not command_carries_trailing_marker(command_text, VERIFY_SKIP_MARKER)


def test_command_carries_trailing_marker_true_with_trailing_words_after_marker() -> None:
    command_text = f"git commit -m x {VERIFY_SKIP_MARKER} please"
    assert command_carries_trailing_marker(command_text, VERIFY_SKIP_MARKER)


def test_command_carries_trailing_marker_false_when_hash_abuts_a_prior_hash() -> None:
    command_text = f"git commit -m x #{VERIFY_SKIP_MARKER}"
    assert not command_carries_trailing_marker(command_text, VERIFY_SKIP_MARKER)


def test_command_carries_trailing_marker_false_when_hash_abuts_a_closing_quote() -> None:
    command_text = f'git commit -m "msg"{VERIFY_SKIP_MARKER}'
    assert not command_carries_trailing_marker(command_text, VERIFY_SKIP_MARKER)


def test_command_carries_trailing_marker_true_when_real_comment_follows_quoted_mention() -> None:
    command_text = f'git commit -m "see {VERIFY_SKIP_MARKER}" {VERIFY_SKIP_MARKER}'
    assert command_carries_trailing_marker(command_text, VERIFY_SKIP_MARKER)


def test_collapse_line_continuations_joins_a_split_git_word() -> None:
    assert collapse_line_continuations("git \\\ncommit -m x") == "git commit -m x"


def test_quoted_spans_finds_each_quoted_region_in_order() -> None:
    all_spans = quoted_spans("git commit -m \"first\" -m 'second'")
    assert len(all_spans) == 2
    assert all_spans[0][0] < all_spans[1][0]


def test_is_inside_quoted_region_true_for_a_position_inside_a_span() -> None:
    command_text = 'echo "Next: git commit"'
    all_spans = quoted_spans(command_text)
    assert is_inside_quoted_region(command_text.index("git"), all_spans)


def test_containing_quoted_span_returns_none_outside_any_quotes() -> None:
    command_text = 'git commit -m "msg"'
    all_spans = quoted_spans(command_text)
    assert containing_quoted_span(command_text.index("git"), all_spans) is None


def test_strip_token_quotes_removes_unpaired_edge_quote() -> None:
    assert strip_token_quotes('push"') == "push"


def test_git_word_match_gates_true_for_a_bare_git_word() -> None:
    command_text = "git commit -m x"
    git_word_match = re.search(r"git", command_text)
    assert git_word_match is not None
    assert git_word_match_gates(git_word_match, command_text, quoted_spans(command_text))


def test_git_word_match_gates_false_for_git_inside_prose() -> None:
    command_text = 'echo "Next: git commit"'
    all_spans = quoted_spans(command_text)
    git_word_match = re.search(r"git", command_text)
    assert git_word_match is not None
    assert not git_word_match_gates(git_word_match, command_text, all_spans)


def test_git_word_match_gates_true_for_a_quoted_git_binary_path() -> None:
    command_text = "& 'C:/x/git.exe' commit -m x"
    all_spans = quoted_spans(command_text)
    git_word_match = re.search(r"git", command_text)
    assert git_word_match is not None
    assert git_word_match_gates(git_word_match, command_text, all_spans)
