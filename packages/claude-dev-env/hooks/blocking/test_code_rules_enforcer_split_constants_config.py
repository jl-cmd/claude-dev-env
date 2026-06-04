"""Behavior tests for the code_rules_constants_config code-rules check module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_constants_config import (  # noqa: E402
    _is_exempt_for_advisory_scan,
    _scan_function_body_constants,
    check_constants_outside_config,
    check_constants_outside_config_advisory,
    check_file_global_constants_use_count,
)

code_rules_enforcer = SimpleNamespace(
    _is_exempt_for_advisory_scan=_is_exempt_for_advisory_scan,
    _scan_function_body_constants=_scan_function_body_constants,
    check_constants_outside_config=check_constants_outside_config,
    check_constants_outside_config_advisory=check_constants_outside_config_advisory,
    check_file_global_constants_use_count=check_file_global_constants_use_count,
)


CONSTANTS_OUTSIDE_CONFIG_PRODUCTION_FILE_PATH = "packages/app/services/encoding.py"

PRODUCTION_FILE_PATH = "packages/claude-dev-env/hooks/blocking/example_production.py"


def test_should_flag_constant_used_only_in_class_level_decorator() -> None:
    source = (
        "TIMEOUT = 5\n"
        "\n"
        "def register(value):\n"
        "    def wrap(cls):\n"
        "        return cls\n"
        "    return wrap\n"
        "\n"
        "@register(TIMEOUT)\n"
        "class Foo:\n"
        "    pass\n"
    )
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert any(
        "TIMEOUT" in issue and "only 1 function/method" in issue for issue in issues
    ), f"Expected class-decorator usage to register as a caller, got: {issues}"


def test_should_flag_constant_used_once_at_module_scope_and_once_in_function() -> None:
    source = "UPPER = 1\nSHADOW = UPPER\n\ndef lonely_caller():\n    return UPPER\n"
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Expected module-scope + function usage to count as 2 distinct callers, got: {issues}"
    )


def test_is_exempt_for_advisory_scan_returns_true_for_config_file() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("project/config/constants.py") is True


def test_is_exempt_for_advisory_scan_returns_true_for_test_file() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("test_example.py") is True


def test_is_exempt_for_advisory_scan_returns_true_for_workflow_registry() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("app/workflow/states.py") is True


def test_is_exempt_for_advisory_scan_returns_true_for_migration() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("app/migrations/0001_initial.py") is True


def test_is_exempt_for_advisory_scan_returns_false_for_production_file() -> None:
    assert code_rules_enforcer._is_exempt_for_advisory_scan("packages/myapp/some_module.py") is False


def test_scan_function_body_constants_finds_upper_snake_in_function() -> None:
    source = (
        "def fetch():\n"
        "    MAX_RETRIES = 3\n"
        "    for attempt in range(MAX_RETRIES):\n"
        "        pass\n"
    )
    advisory_issues = code_rules_enforcer._scan_function_body_constants(source)
    assert any("MAX_RETRIES" in issue for issue in advisory_issues)


def test_scan_function_body_constants_does_not_flag_module_level() -> None:
    source = "MAX_RETRIES = 3\n\ndef fetch():\n    pass\n"
    advisory_issues = code_rules_enforcer._scan_function_body_constants(source)
    assert advisory_issues == []


def test_advisory_should_not_flag_class_attribute_after_method_def() -> None:
    source_with_class_attribute_after_method = (
        "class ExampleModel:\n"
        "    def method_a(self) -> None:\n"
        "        pass\n"
        "\n"
        "    TABLE_NAME = \"example\"\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_class_attribute_after_method,
        "example_module.py",
    )
    assert advisory_issues == [], (
        "Class-level TABLE_NAME attribute must not be flagged as function-local"
    )


def test_advisory_should_still_flag_actual_method_body_constant() -> None:
    source_with_method_body_constant = (
        "class ExampleModel:\n"
        "    def method_a(self) -> None:\n"
        "        MAXIMUM_RETRIES = 3\n"
        "        return None\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_method_body_constant,
        "example_module.py",
    )
    assert len(advisory_issues) == 1, (
        "Method-body UPPER_SNAKE constant must still surface as advisory"
    )
    assert "MAXIMUM_RETRIES" in advisory_issues[0]


def test_advisory_should_flag_annotated_function_body_constant() -> None:
    source_with_annotated_function_body_constant = (
        "def example_function() -> None:\n"
        "    MAXIMUM_RETRIES: int = 3\n"
        "    return None\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_annotated_function_body_constant,
        "example_module.py",
    )
    assert len(advisory_issues) == 1, (
        "Annotated function-body UPPER_SNAKE constant (PEP 526) must surface as advisory"
    )
    assert "MAXIMUM_RETRIES" in advisory_issues[0]


def test_advisory_should_flag_outer_constants_after_nested_def() -> None:
    source_with_nested_def = (
        "def outer():\n"
        "    OUTER_CONST = 1\n"
        "    def inner():\n"
        "        INNER_CONST = 2\n"
        "    ANOTHER_OUTER = 3\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source_with_nested_def,
        "example_module.py",
    )
    flagged_names = " ".join(advisory_issues)
    assert "OUTER_CONST" in flagged_names, (
        "OUTER_CONST before nested def must be flagged"
    )
    assert "INNER_CONST" in flagged_names, (
        "INNER_CONST inside nested def must be flagged"
    )
    assert "ANOTHER_OUTER" in flagged_names, (
        "ANOTHER_OUTER after nested def must be flagged — this is the regression case"
    )


def test_check_constants_outside_config_flags_annotated_assignment() -> None:
    source = "TEXT_FILE_ENCODING: str = 'utf-8'\n"
    issues = code_rules_enforcer.check_constants_outside_config(
        source, CONSTANTS_OUTSIDE_CONFIG_PRODUCTION_FILE_PATH
    )
    assert any("TEXT_FILE_ENCODING" in each_issue for each_issue in issues), (
        f"Expected annotated UPPER_SNAKE assignment flagged, got: {issues}"
    )


def test_check_constants_outside_config_reports_more_than_three_constants() -> None:
    source = (
        "ALPHA_VALUE = 1\n"
        "BETA_VALUE = 2\n"
        "GAMMA_VALUE = 3\n"
        "DELTA_VALUE = 4\n"
        "EPSILON_VALUE = 5\n"
        "\n"
        "def consumer() -> int:\n"
        "    return ALPHA_VALUE + BETA_VALUE\n"
    )
    issues = code_rules_enforcer.check_constants_outside_config(
        source, CONSTANTS_OUTSIDE_CONFIG_PRODUCTION_FILE_PATH
    )
    expected_constant_count = 5
    assert len(issues) == expected_constant_count, (
        f"Expected all {expected_constant_count} constants reported, got {len(issues)}: {issues}"
    )


_SINGLE_CALLER_CONSTANT_SOURCE = (
    "TIMEOUT = 5\n"
    "\n"
    "def lonely_caller() -> int:\n"
    "    return TIMEOUT\n"
)

_ENFORCER_ENTRY_FILE_PATH = "packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py"


def test_use_count_flags_single_caller_constant_for_ordinary_production_path() -> None:
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        _SINGLE_CALLER_CONSTANT_SOURCE, PRODUCTION_FILE_PATH
    )
    assert any(
        "TIMEOUT" in issue and "only 1 function/method" in issue for issue in issues
    ), f"Expected single-caller constant flagged on an ordinary production path, got: {issues}"


def test_use_count_exempts_enforcer_entry_module_path() -> None:
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        _SINGLE_CALLER_CONSTANT_SOURCE, _ENFORCER_ENTRY_FILE_PATH
    )
    assert issues == [], (
        "The enforcer entry module must be exempt to avoid self-blocking, "
        f"got: {issues}"
    )
