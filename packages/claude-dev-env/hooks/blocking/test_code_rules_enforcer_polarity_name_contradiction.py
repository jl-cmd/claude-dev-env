from __future__ import annotations

import importlib.util
from pathlib import Path

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location("code_rules_enforcer", ENFORCER_PATH)
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/foo.py"
TEST_FILE_PATH = "packages/app/tests/test_foo.py"


def test_should_flag_allowed_target_assigned_from_forbidden_callee() -> None:
    source = (
        "def offset() -> None:\n"
        "    is_inside_allowed = _point_hits_any_forbidden(px, py, rects)\n"
        "    return is_inside_allowed\n"
    )
    issues = code_rules_enforcer.check_polarity_name_contradiction(source, PRODUCTION_FILE_PATH)
    assert any("is_inside_allowed" in each_issue for each_issue in issues), (
        f"Expected the allowed/forbidden contradiction flagged, got: {issues}"
    )


def test_should_flag_attribute_callee_with_antonym() -> None:
    source = (
        "def gate() -> None:\n    is_enabled = self._is_disabled(state)\n    return is_enabled\n"
    )
    issues = code_rules_enforcer.check_polarity_name_contradiction(source, PRODUCTION_FILE_PATH)
    assert any("is_enabled" in each_issue for each_issue in issues), (
        f"Expected the enabled/disabled contradiction flagged, got: {issues}"
    )


def test_should_not_flag_when_callee_polarity_matches_target() -> None:
    source = (
        "def gate() -> None:\n"
        "    is_allowed = _point_inside_any_allowed_rect(px, py, rects)\n"
        "    return is_allowed\n"
    )
    issues = code_rules_enforcer.check_polarity_name_contradiction(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Matching polarity must pass, got: {issues}"


def test_should_not_flag_neutral_callee() -> None:
    source = (
        "def gate() -> None:\n"
        "    is_allowed = _point_inside_any_rect(px, py, rects)\n"
        "    return is_allowed\n"
    )
    issues = code_rules_enforcer.check_polarity_name_contradiction(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Neutral callee must pass, got: {issues}"


def test_should_not_flag_substring_only_token_match() -> None:
    source = (
        "def gate() -> None:\n"
        "    is_disallowed_count = compute_blocked_total(rects)\n"
        "    return is_disallowed_count\n"
    )
    issues = code_rules_enforcer.check_polarity_name_contradiction(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"'disallowed' embeds 'allowed' as a substring, not a whole token; must not flag, got: {issues}"
    )


def test_should_skip_in_test_files() -> None:
    source = (
        "def offset() -> None:\n"
        "    is_inside_allowed = _point_hits_any_forbidden(px, py, rects)\n"
        "    return is_inside_allowed\n"
    )
    issues = code_rules_enforcer.check_polarity_name_contradiction(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues}"
