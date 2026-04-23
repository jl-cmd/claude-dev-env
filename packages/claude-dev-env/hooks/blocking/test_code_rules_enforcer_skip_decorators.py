"""Tests for skip-decorator detection in test files.

Tests must fail on missing dependencies rather than silently skip.
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


def test_should_flag_pytest_mark_skip_on_test_function() -> None:
    source = (
        "import pytest\n"
        "\n"
        "@pytest.mark.skip(reason='missing dep')\n"
        "def test_something() -> None:\n"
        "    assert True\n"
    )
    issues = code_rules_enforcer.check_skip_decorators_in_tests(source, TEST_FILE_PATH)
    assert any("skip" in issue.lower() for issue in issues), (
        f"Expected skip decorator issue, got: {issues}"
    )


def test_should_flag_pytest_mark_skipif_on_test_function() -> None:
    source = (
        "import pytest\n"
        "\n"
        "@pytest.mark.skipif(condition, reason='missing')\n"
        "def test_other() -> None:\n"
        "    pass\n"
    )
    issues = code_rules_enforcer.check_skip_decorators_in_tests(source, TEST_FILE_PATH)
    assert any("skip" in issue.lower() for issue in issues), (
        f"Expected skipif decorator issue, got: {issues}"
    )


def test_should_flag_unittest_skip_on_test_function() -> None:
    source = (
        "import unittest\n"
        "\n"
        "@unittest.skip('not ready')\n"
        "def test_thing() -> None:\n"
        "    pass\n"
    )
    issues = code_rules_enforcer.check_skip_decorators_in_tests(source, TEST_FILE_PATH)
    assert any("skip" in issue.lower() for issue in issues), (
        f"Expected unittest.skip issue, got: {issues}"
    )


def test_should_flag_skip_if_missing_dependency_decorator() -> None:
    source = (
        "@skip_if_missing_dependency('requests')\n"
        "def test_with_requests() -> None:\n"
        "    pass\n"
    )
    issues = code_rules_enforcer.check_skip_decorators_in_tests(source, TEST_FILE_PATH)
    assert any("skip" in issue.lower() for issue in issues), (
        f"Expected skip_if_missing_dependency issue, got: {issues}"
    )


def test_should_not_flag_skip_decorators_on_non_test_functions() -> None:
    source = (
        "@pytest.mark.skip(reason='broken')\ndef helper_function() -> None:\n    pass\n"
    )
    issues = code_rules_enforcer.check_skip_decorators_in_tests(source, TEST_FILE_PATH)
    assert issues == [], f"Expected no issues for non-test function, got: {issues}"


def test_should_not_flag_skip_decorators_in_production_files() -> None:
    source = (
        "@pytest.mark.skip(reason='missing dep')\n"
        "def test_something() -> None:\n"
        "    assert True\n"
    )
    issues = code_rules_enforcer.check_skip_decorators_in_tests(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Expected no issues in production file, got: {issues}"


def test_should_include_line_number_in_issue_message() -> None:
    source = (
        "import pytest\n"
        "\n"
        "@pytest.mark.skip(reason='missing dep')\n"
        "def test_flagged() -> None:\n"
        "    pass\n"
    )
    issues = code_rules_enforcer.check_skip_decorators_in_tests(source, TEST_FILE_PATH)
    assert any("Line 3" in issue for issue in issues), (
        f"Expected 'Line 3' in issue, got: {issues}"
    )


def test_should_flag_decorator_with_skip_in_name() -> None:
    source = "@skip_slow_tests\ndef test_slow() -> None:\n    pass\n"
    issues = code_rules_enforcer.check_skip_decorators_in_tests(source, TEST_FILE_PATH)
    assert any("skip" in issue.lower() for issue in issues), (
        f"Expected skip-named decorator issue, got: {issues}"
    )


def test_stops_at_max_issues_per_check() -> None:
    source = (
        "import pytest\n"
        "\n"
        "@pytest.mark.skip(reason='a')\n"
        "def test_one() -> None:\n"
        "    pass\n"
        "\n"
        "@pytest.mark.skip(reason='b')\n"
        "def test_two() -> None:\n"
        "    pass\n"
        "\n"
        "@pytest.mark.skip(reason='c')\n"
        "def test_three() -> None:\n"
        "    pass\n"
        "\n"
        "@pytest.mark.skip(reason='d')\n"
        "def test_four() -> None:\n"
        "    pass\n"
        "\n"
        "@pytest.mark.skip(reason='e')\n"
        "def test_five() -> None:\n"
        "    pass\n"
    )
    issues = code_rules_enforcer.check_skip_decorators_in_tests(source, TEST_FILE_PATH)
    assert len(issues) == code_rules_enforcer.MAX_ISSUES_PER_CHECK
