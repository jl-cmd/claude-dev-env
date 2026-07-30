"""Real command fixtures for the quote-aware shell pipeline parser.

Covers quotes, operators, heredocs, continuations, groups, wrappers, and
compound shells. No pytest-specific classification runs here.
"""

from __future__ import annotations

import pathlib
import sys

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.shell_command_pipeline import (  # noqa: E402
    all_operator_aware_tokenizations,
    join_line_continuations,
    live_command_lines,
    pipeline_segments_for_command,
    scannable_command_lines,
    segments_with_following_operator,
)
from hooks_constants.shell_command_segments import (  # noqa: E402
    split_into_segments,
)


def test_pipe_segments_pair_with_following_operator() -> None:
    all_tokens = ["pytest", "tests", "|", "tee", "out.log"]
    all_pairs = segments_with_following_operator(all_tokens)
    assert all_pairs[0] == (["pytest", "tests"], "|")
    assert all_pairs[1] == (["tee", "out.log"], "")


def test_quoted_pipe_inside_k_expression_stays_in_one_segment() -> None:
    """Quote-aware tokenization keeps pytest -k \"a|b\" as one segment."""
    command = 'pytest -k "a|b" tests'
    all_tokenizations = all_operator_aware_tokenizations(command)
    assert all_tokenizations
    all_pairs = segments_with_following_operator(all_tokenizations[0])
    assert len(all_pairs) == 1
    segment_tokens, following_operator = all_pairs[0]
    assert following_operator == ""
    assert any("a|b" in each_token or each_token == "a|b" for each_token in segment_tokens)


def test_quote_unaware_segments_split_on_pipe_inside_quotes() -> None:
    """Divergence: shell_command_segments peels | inside a|b; quote-aware path does not."""
    all_segments = split_into_segments(["pytest", "-k", "a|b", "tests"])
    assert len(all_segments) > 1
    quote_aware_pairs = pipeline_segments_for_command('pytest -k "a|b" tests')
    assert len(quote_aware_pairs) >= 1
    assert all(each_operator != "|" for _, each_operator in quote_aware_pairs)


def test_heredoc_body_is_dropped_from_live_lines() -> None:
    all_lines = [
        "cat > run.sh <<'EOF'",
        "pytest tests | tee out.log",
        "EOF",
        "echo done",
    ]
    assert live_command_lines(all_lines) == ["cat > run.sh <<'EOF'", "echo done"]


def test_scannable_lines_drop_heredoc_body_and_keep_later_command() -> None:
    command = "cat > run.sh <<'EOF'\npytest tests | tee out.log\nEOF\necho done"
    all_lines = scannable_command_lines(join_line_continuations(command))
    assert "pytest tests | tee out.log" not in all_lines
    assert any("echo done" in each_line for each_line in all_lines)


def test_line_continuation_joins_pipe_onto_one_line() -> None:
    command = "echo hi \\\n| cat"
    joined = join_line_continuations(command)
    assert "\n" not in joined
    assert "| cat" in joined


def test_comment_does_not_hide_following_line() -> None:
    command = "echo hi  # note\necho bye"
    all_lines = scannable_command_lines(command)
    assert any("echo bye" in each_line for each_line in all_lines)
    assert all("# note" not in each_line for each_line in all_lines)


def test_paren_group_joins_multiline_subshell_before_pipe() -> None:
    command = "(\necho hi\n) | cat"
    all_lines = scannable_command_lines(command)
    assert len(all_lines) == 1
    assert "|" in all_lines[0]
    assert "echo hi" in all_lines[0]


def test_glued_close_paren_and_pipe_split_into_operator_token() -> None:
    all_pairs = segments_with_following_operator(["(", "echo", "hi", ")|", "cat"])
    assert any(each_operator == "|" for _, each_operator in all_pairs)


def test_and_operator_resets_segment() -> None:
    all_pairs = segments_with_following_operator(
        ["echo", "a", "&&", "echo", "b"]
    )
    assert all_pairs[0] == (["echo", "a"], "&&")
    assert all_pairs[1][0] == ["echo", "b"]


def test_pipeline_segments_for_command_on_simple_pipe() -> None:
    all_pairs = pipeline_segments_for_command("echo hi | cat")
    leading_programs = [
        each_segment[0] for each_segment, _ in all_pairs if each_segment
    ]
    assert "echo" in leading_programs
    assert "cat" in leading_programs
    assert any(each_operator == "|" for _, each_operator in all_pairs)


def test_wrapper_tokens_remain_visible_in_segment() -> None:
    """Wrappers stay in the segment; classification is a later slice."""
    all_pairs = pipeline_segments_for_command("sudo -n echo hi | cat")
    first_pipe_segment = next(
        each_segment for each_segment, each_operator in all_pairs if each_operator == "|"
    )
    assert first_pipe_segment[0] in {"sudo", "sudo.exe"} or "sudo" in first_pipe_segment[0]


def test_compound_shell_if_fi_tokens_survive_tokenization() -> None:
    command = "if true; then echo hi; fi"
    all_tokenizations = all_operator_aware_tokenizations(command)
    assert all_tokenizations
    flat_tokens = all_tokenizations[0]
    assert "if" in flat_tokens
    assert "then" in flat_tokens
    assert "fi" in flat_tokens
