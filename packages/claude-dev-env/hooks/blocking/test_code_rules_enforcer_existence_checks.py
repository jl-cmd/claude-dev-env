"""Tests for existence-check test detection.

Tests that only assert callable(x), hasattr(m, 'name'), or
x is not None without any behavior validation are useless and
should be deleted or replaced.
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

TEST_FILE_PATH = "packages/app/tests/test_feature.py"
PRODUCTION_FILE_PATH = "packages/app/services/feature.py"


def test_should_flag_test_with_only_callable_assertion() -> None:
    source = "def test_function_exists() -> None:\n    assert callable(my_function)\n"
    issues = code_rules_enforcer.check_existence_check_tests(source, TEST_FILE_PATH)
    assert any("existence" in issue.lower() for issue in issues), (
        f"Expected existence-check issue, got: {issues}"
    )


def test_should_flag_test_with_only_hasattr_assertion() -> None:
    source = (
        "def test_module_has_attribute() -> None:\n"
        '    assert hasattr(module, "my_attr")\n'
    )
    issues = code_rules_enforcer.check_existence_check_tests(source, TEST_FILE_PATH)
    assert any("existence" in issue.lower() for issue in issues), (
        f"Expected existence-check issue, got: {issues}"
    )


def test_should_flag_test_with_only_is_not_none_assertion() -> None:
    source = (
        "def test_instance_created() -> None:\n"
        "    instance = MyClass()\n"
        "    assert instance is not None\n"
    )
    issues = code_rules_enforcer.check_existence_check_tests(source, TEST_FILE_PATH)
    assert any("existence" in issue.lower() for issue in issues), (
        f"Expected existence-check issue for is-not-None test, got: {issues}"
    )


def test_should_not_flag_test_with_behavior_assertions() -> None:
    source = (
        "def test_function_returns_expected_value() -> None:\n"
        "    actual_result = compute(input_value)\n"
        "    assert actual_result == expected_value\n"
    )
    issues = code_rules_enforcer.check_existence_check_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issues for behavior test, got: {issues}"


def test_should_not_flag_test_with_multiple_assertions() -> None:
    source = (
        "def test_function_callable_and_returns_int() -> None:\n"
        "    assert callable(my_function)\n"
        "    assert isinstance(my_function(), int)\n"
    )
    issues = code_rules_enforcer.check_existence_check_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issues for multi-assertion test, got: {issues}"


def test_should_not_flag_existence_checks_in_production_files() -> None:
    source = "def test_function_exists() -> None:\n    assert callable(my_function)\n"
    issues = code_rules_enforcer.check_existence_check_tests(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Expected no issues in production file, got: {issues}"


def test_should_include_line_number_in_issue() -> None:
    source = "\n\ndef test_callable_check() -> None:\n    assert callable(func)\n"
    issues = code_rules_enforcer.check_existence_check_tests(source, TEST_FILE_PATH)
    assert any("Line 3" in issue for issue in issues), (
        f"Expected 'Line 3' in issue, got: {issues}"
    )


def test_should_not_flag_non_test_function_with_existence_check() -> None:
    source = "def helper_with_callable_check() -> None:\n    assert callable(func)\n"
    issues = code_rules_enforcer.check_existence_check_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issues for non-test function, got: {issues}"


def test_should_not_flag_outer_test_when_nested_helper_contains_existence_check() -> None:
    source = (
        "def test_outer_behavior() -> None:\n"
        "    if True:\n"
        "        def nested_helper() -> None:\n"
        "            assert callable(some_function)\n"
        "    assert 1 + 1 == 2\n"
    )
    issues = code_rules_enforcer.check_existence_check_tests(source, TEST_FILE_PATH)
    assert issues == [], (
        f"Expected no issues: nested helper's callable assertion must not count"
        f" against the outer test, got: {issues}"
    )
