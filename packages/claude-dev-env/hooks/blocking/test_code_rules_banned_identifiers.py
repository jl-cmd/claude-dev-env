"""Tests for blast-radius suffix exemption on the banned-noun word check."""

from __future__ import annotations

from code_rules_banned_identifiers import (
    _find_banned_noun_word,
    check_banned_noun_word_boundary,
)

PRODUCTION_FILE_PATH = "packages/app/services/customer_pipeline.py"


def test_should_return_no_banned_word_for_item_blocked_exception_suffix() -> None:
    assert _find_banned_noun_word("AssetSizingItemBlocked") is None
    assert _find_banned_noun_word("NinePatchGuideFrameItemBlocked") is None


def test_should_return_no_banned_word_for_run_fatal_exception_suffix() -> None:
    assert _find_banned_noun_word("AssetVariantRunFatal") is None


def test_should_return_banned_word_for_item_without_blast_radius_suffix() -> None:
    assert _find_banned_noun_word("IconGridItem") == "item"
    assert _find_banned_noun_word("item_key") == "item"


def test_should_allow_class_ending_with_item_blocked_suffix() -> None:
    source = "class AssetSizingItemBlocked(Exception):\n    pass\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_long_class_ending_with_item_blocked_suffix() -> None:
    source = "class NinePatchGuideFrameItemBlocked(Exception):\n    pass\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_allow_class_ending_with_run_fatal_suffix() -> None:
    source = "class AssetVariantRunFatal(Exception):\n    pass\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_flag_class_ending_with_item_without_blast_radius_suffix() -> None:
    source = "class IconGridItem:\n    pass\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("IconGridItem" in each_issue for each_issue in issues)


def test_should_flag_item_key_assignment() -> None:
    source = "item_key = 'slot'\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("item_key" in each_issue for each_issue in issues)


def test_should_flag_output_path_assignment() -> None:
    source = "output_path = 'slot'\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("output_path" in each_issue for each_issue in issues)


def test_should_flag_each_value_assignment() -> None:
    source = "each_value = 1\n"
    issues = check_banned_noun_word_boundary(source, PRODUCTION_FILE_PATH)
    assert any("each_value" in each_issue for each_issue in issues)
