"""Behavior tests for pr_description_enforcer_constants module."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants import pr_description_enforcer_constants as constants_module


def test_plugin_root_is_private_module_attribute() -> None:
    assert hasattr(constants_module, "_PLUGIN_ROOT")
    assert isinstance(constants_module._PLUGIN_ROOT, str)
    assert os.path.isabs(constants_module._PLUGIN_ROOT)


def test_plugin_root_public_name_is_not_exported() -> None:
    assert not hasattr(constants_module, "PLUGIN_ROOT")


def test_pr_guide_path_resolves_under_plugin_root_docs() -> None:
    expected_pr_guide_path = os.path.join(
        constants_module._PLUGIN_ROOT, "docs", "PR_DESCRIPTION_GUIDE.md"
    )
    assert constants_module.PR_GUIDE_PATH == expected_pr_guide_path


def test_fenced_code_block_pattern_matches_triple_backtick_block() -> None:
    sample_markdown = "before ```python\ncode\n``` after"
    match = constants_module.FENCED_CODE_BLOCK_PATTERN.search(sample_markdown)
    assert match is not None
    assert match.group(0).startswith("```")
    assert match.group(0).endswith("```")


def test_inline_code_pattern_matches_single_backtick_span() -> None:
    match = constants_module.INLINE_CODE_PATTERN.search("see `value` here")
    assert match is not None
    assert match.group(0) == "`value`"


def test_heading_line_pattern_matches_atx_heading() -> None:
    match = constants_module.HEADING_LINE_PATTERN.search("## Description\n")
    assert match is not None
    assert match.group(0).strip() == "## Description"


def test_bold_pair_pattern_captures_inner_text() -> None:
    match = constants_module.BOLD_PAIR_PATTERN.search("this is **bold** text")
    assert match is not None
    assert match.group(1) == "bold"


def test_bullet_marker_pattern_strips_dash_bullet_from_line() -> None:
    stripped_line = constants_module.BULLET_MARKER_PATTERN.sub("", "- first item")
    assert stripped_line == "first item"


def test_blockquote_marker_pattern_strips_quote_marker_from_line() -> None:
    stripped_line = constants_module.BLOCKQUOTE_MARKER_PATTERN.sub("", "> quoted line")
    assert stripped_line == "quoted line"


def test_link_text_pattern_captures_anchor_text() -> None:
    match = constants_module.LINK_TEXT_PATTERN.search("See [the docs](https://example.com) now")
    assert match is not None
    assert match.group(1) == "the docs"


def test_whitespace_run_pattern_collapses_multiple_spaces() -> None:
    collapsed_text = constants_module.WHITESPACE_RUN_PATTERN.sub(" ", "a   b\t\tc\n\nd")
    assert collapsed_text == "a b c d"


def test_this_pr_opening_pattern_matches_any_verb() -> None:
    """The guide says any `This PR ...` opening is a hard block. The pattern
    must match regardless of the verb that follows, not a short allowlist."""
    test_inputs = [
        "This PR introduces a new feature.",
        "This PR improves the algorithm.",
        "This PR enables the cache.",
        "This PR documents the contract.",
        "This PR adds a check.",
        "This PR fixes the bug.",
    ]
    for each_input in test_inputs:
        assert constants_module.THIS_PR_OPENING_PATTERN.match(each_input), (
            f"`{each_input}` must match THIS_PR_OPENING_PATTERN regardless of verb"
        )


def test_this_pr_opening_pattern_does_not_match_within_prose() -> None:
    """The block applies to body openings, not mid-paragraph mentions."""
    text_with_mid_mention = "Adds caching. This PR follows the playbook."
    assert constants_module.THIS_PR_OPENING_PATTERN.match(text_with_mid_mention) is None


def test_all_list_is_alphabetically_sorted() -> None:
    """`__all__` is the export surface; alphabetical order makes it easy to
    verify completeness, spot duplicates, and bisect missing entries. Pin
    sorted order so drift cannot reintroduce the H-before-G / appended-at-end
    inconsistencies Bugbot flagged."""
    actual_all_list = constants_module.__all__
    expected_sorted = sorted(actual_all_list)
    if actual_all_list != expected_sorted:
        first_divergence_index = next(
            each_index
            for each_index, (each_actual_value, each_expected_value) in enumerate(zip(actual_all_list, expected_sorted))
            if each_actual_value != each_expected_value
        )
        raise AssertionError(
            "constants_module.__all__ must be alphabetically sorted; "
            f"the first divergence is at index {first_divergence_index}: "
            f"got {actual_all_list[first_divergence_index]!r}, "
            f"expected {expected_sorted[first_divergence_index]!r}"
        )


def test_dead_heavy_detection_constants_are_removed() -> None:
    """`ALL_HEAVY_DETECTION_HEADERS` and `HEAVY_DETECTION_HEADER_COUNT_MIN`
    were remnants of the prior two-condition shape classifier (length AND
    detection-header count). e137dee9 simplified the classifier to use length
    alone, leaving both names as dead exports. Pin their removal so they
    cannot drift back as misleading vestigial constants."""
    for each_name in ("ALL_HEAVY_DETECTION_HEADERS", "HEAVY_DETECTION_HEADER_COUNT_MIN"):
        assert not hasattr(constants_module, each_name), (
            f"{each_name} must be deleted; the classifier now uses "
            "HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION alone."
        )
        assert each_name not in constants_module.__all__


def test_self_closing_reference_message_prefix_and_suffix_compose_full_message() -> None:
    pr_number = 42
    composed_message = (
        f"{constants_module.SELF_CLOSING_REFERENCE_MESSAGE_PREFIX}"
        f"{pr_number}"
        f"{constants_module.SELF_CLOSING_REFERENCE_MESSAGE_SUFFIX}"
    )
    assert "#42" in composed_message
    assert "Fixes/Closes/Resolves" in composed_message
    assert "self-reference" in composed_message


def test_loosen_factors_are_inverse_paired() -> None:
    flesch_factor = constants_module.READABILITY_FLESCH_LOOSEN_FACTOR
    sentence_factor = constants_module.READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR
    assert flesch_factor * sentence_factor == pytest.approx(1.0)


def test_unused_header_constants_are_removed_from_module() -> None:
    """The four header constants FIX_HEADER, CHANGES_HEADER, APPROACH_HEADER,
    and ROOT_CAUSE_HEADER were dead exports with no call sites and must not be
    re-introduced as either module attributes or __all__ entries."""
    for each_dead_name in ("FIX_HEADER", "CHANGES_HEADER", "APPROACH_HEADER", "ROOT_CAUSE_HEADER"):
        assert not hasattr(constants_module, each_dead_name), (
            f"{each_dead_name} was re-introduced; the four header constants "
            "had zero call sites and were deleted."
        )
        assert each_dead_name not in constants_module.__all__, (
            f"{each_dead_name} re-appeared in __all__ even though it has no consumers."
        )


def test_module_internal_header_constants_are_not_publicly_exported() -> None:
    """The seven header-name constants and three default-readability-threshold scalars
    are consumed only inside this same module (used to build ALL_HEAVY_* frozensets
    and DEFAULT_READABILITY_THRESHOLDS). They must remain module attributes for the
    builder expressions, but they must NOT appear in __all__ -- callers should import
    the public aggregates (ALL_HEAVY_OPENING_HEADERS / ALL_HEAVY_TESTING_HEADERS /
    DEFAULT_READABILITY_THRESHOLDS) instead of the individual scalars."""
    all_internal_only_names = (
        "SUMMARY_HEADER",
        "PROBLEM_HEADER",
        "TEST_PLAN_HEADER",
        "TESTS_HEADER",
        "TESTING_HEADER",
        "VERIFICATION_HEADER",
        "VALIDATION_HEADER",
        "READABILITY_MAX_SENTENCE_WORDS",
        "READABILITY_AVG_SENTENCE_WORDS",
        "READABILITY_MIN_FLESCH",
    )
    for each_internal_name in all_internal_only_names:
        assert hasattr(constants_module, each_internal_name), (
            f"{each_internal_name} must remain as a module attribute -- "
            "the aggregate builders reference it."
        )
        assert each_internal_name not in constants_module.__all__, (
            f"{each_internal_name} is consumed only inside the module and "
            "must not be advertised in __all__."
        )


def test_self_reference_pattern_covers_all_nine_github_closing_keywords() -> None:
    """GitHub recognizes nine closing keywords: close/closes/closed,
    fix/fixes/fixed, resolve/resolves/resolved. The self-reference template
    must enumerate all nine so no variant bypasses the self-closing block."""
    pattern_source = constants_module.SELF_REFERENCE_PATTERN_TEMPLATE
    for each_keyword in (
        "Close", "Closes", "Closed",
        "Fix", "Fixes", "Fixed",
        "Resolve", "Resolves", "Resolved",
    ):
        assert each_keyword in pattern_source, (
            f"SELF_REFERENCE_PATTERN_TEMPLATE must enumerate `{each_keyword}` "
            f"to catch every GitHub closing-keyword variant; got: {pattern_source!r}"
        )


def test_body_shape_string_literals_are_named_constants() -> None:
    """The three PR-body shape names (`trivial`, `standard`, `heavy`) are used
    by both `_compute_pr_body_shape` (return values) and `validate_pr_body`
    (string comparisons). Bugbot flagged the inline literals as cross-function
    magic strings. Pin the canonical names in `hooks_constants/` so a typo in
    either site cannot silently misclassify shape."""
    assert constants_module.TRIVIAL_SHAPE == "trivial"
    assert constants_module.STANDARD_SHAPE == "standard"
    assert constants_module.HEAVY_SHAPE == "heavy"
    for each_name in ("TRIVIAL_SHAPE", "STANDARD_SHAPE", "HEAVY_SHAPE"):
        assert each_name in constants_module.__all__


def test_readability_cli_flag_tokens_exposes_four_flags() -> None:
    """ALL_READABILITY_CLI_FLAG_TOKENS centralises the four CLI flags the
    dispatcher recognises (loosen/reset/disable/enable). Pinning the set keeps
    main()'s dispatcher loop and the dispatcher itself in sync; adding a flag
    requires updating both the constant and the dispatcher in the same commit."""
    expected_tokens = frozenset(
        {
            "--readability-loosen",
            "--readability-reset",
            "--readability-disable",
            "--readability-enable",
        }
    )
    assert constants_module.ALL_READABILITY_CLI_FLAG_TOKENS == expected_tokens
    assert "ALL_READABILITY_CLI_FLAG_TOKENS" in constants_module.__all__


def test_ceremony_header_pattern_is_removed() -> None:
    """`CEREMONY_HEADER_PATTERN` is replaced by the broader `HEADING_LINE_PATTERN`
    check in the Trivial-ceremony violation; the constant must not linger as a
    dead export to drift back into use."""
    assert not hasattr(constants_module, "CEREMONY_HEADER_PATTERN"), (
        "CEREMONY_HEADER_PATTERN must be deleted; the ceremony-on-Trivial check "
        "now uses HEADING_LINE_PATTERN to cover every heading level."
    )
    assert "CEREMONY_HEADER_PATTERN" not in constants_module.__all__


def test_flesch_formula_coefficients_are_named_constants() -> None:
    """The Flesch Reading Ease formula coefficients (206.835, 1.015, 84.6) and
    the perfect-score default (100.0) must live as named UPPER_SNAKE constants
    in `hooks_constants/pr_description_enforcer_constants.py` so the production
    function body has zero magic numeric literals."""
    assert constants_module.FLESCH_BASE_SCORE == 206.835
    assert constants_module.FLESCH_WORDS_PER_SENTENCE_COEFFICIENT == 1.015
    assert constants_module.FLESCH_SYLLABLES_PER_WORD_COEFFICIENT == 84.6
    assert constants_module.FLESCH_PERFECT_SCORE == 100.0
    for each_name in (
        "FLESCH_BASE_SCORE",
        "FLESCH_WORDS_PER_SENTENCE_COEFFICIENT",
        "FLESCH_SYLLABLES_PER_WORD_COEFFICIENT",
        "FLESCH_PERFECT_SCORE",
    ):
        assert each_name in constants_module.__all__, (
            f"{each_name} must appear in __all__ so the enforcer can import it."
        )


def test_all_heavy_testing_headers_enumerates_five_canonical_forms() -> None:
    """The frozenset ALL_HEAVY_TESTING_HEADERS drives the violation message that
    tells the writer which headers satisfy the heavy-shape testing-category
    requirement. The set must include all five canonical forms (Test plan,
    Testing, Tests, Verification, Validation) so the writer's documented
    vocabulary matches the message it receives on a violation."""
    expected_canonical_headers = [
        "## Test plan",
        "## Testing",
        "## Tests",
        "## Validation",
        "## Verification",
    ]
    assert sorted(constants_module.ALL_HEAVY_TESTING_HEADERS) == expected_canonical_headers
