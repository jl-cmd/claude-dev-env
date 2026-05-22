"""Behavior tests for open_questions_in_plans_blocker_constants module."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants import open_questions_in_plans_blocker_constants as constants_module


def test_markdown_extension_is_lowercase_dot_md() -> None:
    assert constants_module.MARKDOWN_EXTENSION == ".md"
    assert "MARKDOWN_EXTENSION" in constants_module.__all__


def test_plans_path_segment_matches_nested_plans_directory() -> None:
    assert constants_module.PLANS_PATH_SEGMENT == "/.claude/plans/"
    assert "PLANS_PATH_SEGMENT" in constants_module.__all__


def test_plans_path_prefix_matches_project_local_plans_directory() -> None:
    assert constants_module.PLANS_PATH_PREFIX == ".claude/plans/"
    assert "PLANS_PATH_PREFIX" in constants_module.__all__


def test_open_questions_heading_pattern_matches_atx_heading() -> None:
    assert constants_module.OPEN_QUESTIONS_HEADING_PATTERN.search("## Open Questions\n")


def test_open_questions_heading_pattern_matches_bold_heading() -> None:
    assert constants_module.OPEN_QUESTIONS_HEADING_PATTERN.search("**Open Questions**\n")


def test_open_questions_heading_pattern_matches_underscore_bold_heading() -> None:
    assert constants_module.OPEN_QUESTIONS_HEADING_PATTERN.search("__Open Questions__\n")


def test_open_questions_heading_pattern_is_case_insensitive() -> None:
    assert constants_module.OPEN_QUESTIONS_HEADING_PATTERN.search("# open questions\n")


def test_open_questions_heading_pattern_does_not_match_concatenated_word() -> None:
    assert constants_module.OPEN_QUESTIONS_HEADING_PATTERN.search("## OpenQuestions\n") is None


def test_open_questions_heading_pattern_does_not_match_longer_word() -> None:
    assert constants_module.OPEN_QUESTIONS_HEADING_PATTERN.search("## Open Questionable\n") is None


def test_open_questions_heading_pattern_in_export_list() -> None:
    assert "OPEN_QUESTIONS_HEADING_PATTERN" in constants_module.__all__


def test_code_fence_pattern_matches_triple_backtick_block() -> None:
    fenced_block_sample = "```markdown\n## Open Questions\n- placeholder\n```"
    assert constants_module.CODE_FENCE_PATTERN.fullmatch(fenced_block_sample)


def test_code_fence_pattern_is_non_greedy_across_two_blocks() -> None:
    two_blocks_sample = "```first```\n\n```second```"
    all_matches = constants_module.CODE_FENCE_PATTERN.findall(two_blocks_sample)
    assert all_matches == ["```first```", "```second```"]


def test_code_fence_pattern_in_export_list() -> None:
    assert "CODE_FENCE_PATTERN" in constants_module.__all__


def test_inline_code_pattern_matches_single_backtick_span() -> None:
    assert constants_module.INLINE_CODE_PATTERN.fullmatch("`code`")


def test_inline_code_pattern_matches_double_backtick_span() -> None:
    assert constants_module.INLINE_CODE_PATTERN.fullmatch("``double tick span``")


def test_inline_code_pattern_does_not_cross_newlines() -> None:
    """CommonMark inline-code spans cannot cross newlines. A stray opening backtick
    followed later by another backtick must NOT be treated as a single inline-code
    span — otherwise the inline-code stripper deletes everything between the two
    backticks, including any text that lives on intervening lines."""
    stray_backtick_sample = "stray `here.\n\nreal heading.\n\nmore `code`"
    all_matches = constants_module.INLINE_CODE_PATTERN.findall(stray_backtick_sample)
    assert all_matches == ["`code`"]


def test_inline_code_pattern_does_not_match_span_spanning_newlines() -> None:
    multiline_span_sample = "`opens here\nbut never closes on the same line`"
    assert constants_module.INLINE_CODE_PATTERN.search(multiline_span_sample) is None


def test_inline_code_pattern_in_export_list() -> None:
    assert "INLINE_CODE_PATTERN" in constants_module.__all__


def test_plan_file_encoding_is_utf8() -> None:
    assert constants_module.PLAN_FILE_ENCODING == "utf-8"
    assert "PLAN_FILE_ENCODING" in constants_module.__all__


def test_unreadable_file_synthetic_content_triggers_heading_pattern() -> None:
    """The synthetic content used when an existing plan file cannot be read must
    contain a heading the open-questions regex matches. This guarantees the
    downstream scan denies the write rather than silently passing."""
    synthetic = constants_module.UNREADABLE_FILE_SYNTHETIC_CONTENT
    assert constants_module.OPEN_QUESTIONS_HEADING_PATTERN.search(synthetic)
    assert "UNREADABLE_FILE_SYNTHETIC_CONTENT" in constants_module.__all__


def test_all_exports_enumerates_eight_public_constants_in_sorted_order() -> None:
    expected_exports = [
        "CODE_FENCE_PATTERN",
        "INLINE_CODE_PATTERN",
        "MARKDOWN_EXTENSION",
        "OPEN_QUESTIONS_HEADING_PATTERN",
        "PLANS_PATH_PREFIX",
        "PLANS_PATH_SEGMENT",
        "PLAN_FILE_ENCODING",
        "UNREADABLE_FILE_SYNTHETIC_CONTENT",
    ]
    assert constants_module.__all__ == expected_exports
