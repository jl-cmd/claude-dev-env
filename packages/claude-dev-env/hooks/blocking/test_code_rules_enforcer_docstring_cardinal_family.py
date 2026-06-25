"""Tests for check_docstring_cardinal_count_matches_constant_family — O6 drift.

A docstring states a cardinal count of an outcome family ("Covers the four
outcome branches: ...") and enumerates the family members in prose, while the
module references more members of that constant family than the count names. The
prose under-describes the code: a reader trusts "four" and the list to be the
full set, but the module imports and exercises a fifth outcome. This is the
deterministic cardinal-count slice of Category O6 docstring-prose-vs-
implementation drift, the shape that appears when a producer adds an outcome
branch but leaves the test-module summary at the old count. The check runs on
test files because the drift class lives in a test-module docstring.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_docstring_cardinal_count_matches_constant_family(
    content: str, file_path: str
) -> list[str]:
    return code_rules_enforcer.check_docstring_cardinal_count_matches_constant_family(
        content, file_path
    )


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/dropdown_fix_rule.py"
TEST_FILE_PATH = "/project/src/tests/test_dropdown_fix_rule.py"


def _test_module(summary_line: str, enumeration_line: str) -> str:
    return (
        '"""Behavioral tests for classify_dropdown_fix.\n'
        "\n"
        f"{summary_line}\n"
        f"{enumeration_line}\n"
        '"""\n'
        "\n"
        "from stp_dropdown_color_fix.config.status_codes import (\n"
        "    OUTCOME_ALREADY_OK,\n"
        "    OUTCOME_OFFENDER_LOW_CONTRAST,\n"
        "    OUTCOME_OFFENDER_MISSING,\n"
        "    OUTCOME_OFFENDER_UNREADABLE,\n"
        "    OUTCOME_SKIPPED_NO_SAFE_SOURCE,\n"
        ")\n"
        "\n"
        "def test_skipped() -> None:\n"
        "    assert classify() == OUTCOME_SKIPPED_NO_SAFE_SOURCE\n"
        "\n"
        "def test_missing() -> None:\n"
        "    assert classify() == OUTCOME_OFFENDER_MISSING\n"
        "\n"
        "def test_low_contrast() -> None:\n"
        "    assert classify() == OUTCOME_OFFENDER_LOW_CONTRAST\n"
        "\n"
        "def test_already_ok() -> None:\n"
        "    assert classify() == OUTCOME_ALREADY_OK\n"
        "\n"
        "def test_unreadable() -> None:\n"
        "    assert classify() == OUTCOME_OFFENDER_UNREADABLE\n"
    )


def _drifted_module() -> str:
    return _test_module(
        "Covers the four outcome branches: skipped_no_safe_source,",
        "offender_missing (case A), offender_low_contrast (case B), already_ok.",
    )


def _matching_module() -> str:
    return _test_module(
        "Covers the five outcome branches: skipped_no_safe_source, offender_missing,",
        "offender_low_contrast, already_ok, offender_unreadable.",
    )


def test_should_flag_test_module_omitting_an_outcome() -> None:
    issues = check_docstring_cardinal_count_matches_constant_family(
        _drifted_module(), TEST_FILE_PATH
    )
    assert any("offender_unreadable" in each for each in issues), (
        "A test-module docstring claiming four outcome branches while the module "
        f"references five OUTCOME_ constants must be flagged, got: {issues!r}"
    )


def test_should_report_category_o6_in_the_message() -> None:
    issues = check_docstring_cardinal_count_matches_constant_family(
        _drifted_module(), TEST_FILE_PATH
    )
    assert any("O6" in each for each in issues), (
        f"Expected the Category O6 label in the message, got: {issues!r}"
    )


def test_should_also_flag_production_module() -> None:
    issues = check_docstring_cardinal_count_matches_constant_family(
        _drifted_module(), PRODUCTION_FILE_PATH
    )
    assert issues != [], (
        f"The cardinal drift must be flagged on a production file too, got: {issues!r}"
    )


def test_should_not_flag_when_count_and_enumeration_match_family() -> None:
    issues = check_docstring_cardinal_count_matches_constant_family(
        _matching_module(), TEST_FILE_PATH
    )
    assert issues == [], (
        f"A docstring naming all five referenced outcomes must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_without_a_cardinal_phrase() -> None:
    source = _test_module(
        "Covers these outcome branches: skipped_no_safe_source,",
        "offender_missing, offender_low_contrast, already_ok.",
    )
    issues = check_docstring_cardinal_count_matches_constant_family(source, TEST_FILE_PATH)
    assert issues == [], (
        f"An enumeration with no cardinal count word must not bind, got: {issues!r}"
    )


def test_should_not_flag_single_passing_mention() -> None:
    source = _test_module(
        "Asserts the four guard paths reach already_ok when the dropdown is",
        "absent and the dialer keeps its painted swatch.",
    )
    issues = check_docstring_cardinal_count_matches_constant_family(source, TEST_FILE_PATH)
    assert issues == [], f"A single overlapping token must not bind the family, got: {issues!r}"


def test_should_not_flag_when_family_has_one_referenced_member() -> None:
    source = (
        '"""Covers the four outcome branches: already_ok, more, words, here."""\n'
        "from status_codes import OUTCOME_ALREADY_OK\n"
        "\n"
        "def test_only() -> None:\n"
        "    assert classify() == OUTCOME_ALREADY_OK\n"
    )
    issues = check_docstring_cardinal_count_matches_constant_family(source, TEST_FILE_PATH)
    assert issues == [], f"A family with one referenced member must not bind, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_cardinal_count_matches_constant_family("def fetch(\n", TEST_FILE_PATH)
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_cardinal_family_drift() -> None:
    issues = validate_content(_drifted_module(), TEST_FILE_PATH, old_content="")
    matching_issues = [each for each in issues if "offender_unreadable" in each and "O6" in each]
    assert matching_issues, (
        f"Expected validate_content to surface the O6 cardinal-family drift, got: {issues!r}"
    )
