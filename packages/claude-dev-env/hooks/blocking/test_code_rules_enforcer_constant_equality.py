"""Tests for constant-value test detection.

Tests that assert a constant equals a literal cover nothing about
behavior and should be deleted.
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

TEST_FILE_PATH = "packages/app/tests/test_constants.py"
PRODUCTION_FILE_PATH = "packages/app/services/feature.py"


def test_should_flag_test_asserting_constant_equals_literal() -> None:
    source = (
        'CACHE_DIR = "cache"\n'
        "\n"
        "def test_cache_dir_value() -> None:\n"
        '    assert CACHE_DIR == "cache"\n'
    )
    issues = code_rules_enforcer.check_constant_equality_tests(source, TEST_FILE_PATH)
    assert any("constant" in issue.lower() for issue in issues), (
        f"Expected constant-value test issue, got: {issues}"
    )


def test_should_flag_test_with_single_upper_snake_equality() -> None:
    source = (
        "MAX_SIZE = 100\n"
        "\n"
        "def test_max_size_is_100() -> None:\n"
        "    assert MAX_SIZE == 100\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(source, TEST_FILE_PATH)
    assert any("constant" in issue.lower() for issue in issues), (
        f"Expected constant-value test issue, got: {issues}"
    )


def test_should_not_flag_test_asserting_computed_result() -> None:
    source = (
        "def test_compute_returns_expected() -> None:\n"
        "    computed_value = compute()\n"
        "    assert computed_value == EXPECTED_OUTPUT\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issues for behavior test, got: {issues}"


def test_should_not_flag_test_with_multiple_assertions() -> None:
    source = (
        "TIMEOUT = 30\n"
        "\n"
        "def test_timeout_used_in_connection() -> None:\n"
        "    assert TIMEOUT == 30\n"
        "    connection = connect(timeout=TIMEOUT)\n"
        "    assert connection.is_alive()\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issues for multi-assertion test, got: {issues}"


def test_should_not_flag_in_production_files() -> None:
    source = (
        "CACHE_DIR = 'cache'\n"
        "\n"
        "def test_something() -> None:\n"
        "    assert CACHE_DIR == 'cache'\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Expected no issues in production file, got: {issues}"


def test_should_include_line_number_in_issue() -> None:
    source = (
        '\n\ndef test_my_constant_value() -> None:\n    assert MY_CONST == "value"\n'
    )
    issues = code_rules_enforcer.check_constant_equality_tests(source, TEST_FILE_PATH)
    assert any("Line 3" in issue for issue in issues), (
        f"Expected 'Line 3' in issue, got: {issues}"
    )


def test_should_not_flag_non_test_function() -> None:
    source = (
        "TIMEOUT = 30\n"
        "\n"
        "def check_constant_value() -> None:\n"
        "    assert TIMEOUT == 30\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issues for non-test function, got: {issues}"


def test_stops_at_max_issues_per_check() -> None:
    source = (
        "ALPHA = 1\nBETA = 2\nGAMMA = 3\nDELTA = 4\nEPSILON = 5\n"
        "\n"
        "def test_alpha() -> None:\n    assert ALPHA == 1\n"
        "\n"
        "def test_beta() -> None:\n    assert BETA == 2\n"
        "\n"
        "def test_gamma() -> None:\n    assert GAMMA == 3\n"
        "\n"
        "def test_delta() -> None:\n    assert DELTA == 4\n"
        "\n"
        "def test_epsilon() -> None:\n    assert EPSILON == 5\n"
    )
    issues = code_rules_enforcer.check_constant_equality_tests(source, TEST_FILE_PATH)
    assert len(issues) == code_rules_enforcer.MAX_ISSUES_PER_CHECK, (
        f"Expected exactly MAX_ISSUES_PER_CHECK issues, got {len(issues)}: {issues}"
    )
