"""Tests covering file-global constant reference resolution edge cases.

Loop2-C: class-decorator usage of a module-level constant must count as a
caller so the single-caller rule fires correctly.

Loop2-D: module-scope usages must register as a distinct caller bucket so
the "zero function references" exemption does not swallow real references.
"""

from __future__ import annotations

import importlib.util
import sys
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

_BLOCKING_DIR = Path(__file__).resolve().parent
if str(_BLOCKING_DIR) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIR))

from code_rules_path_utils import is_config_file as path_utils_is_config_file  # noqa: E402

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


def test_is_config_file_rejects_filename_only_config_pattern() -> None:
    """Paths where 'config' appears only in the filename (not as a directory segment) must return False."""
    assert code_rules_enforcer.is_config_file("scripts/db/config.py") is False, (
        "scripts/db/config.py — filename is config.py but parent dir is db, must be False"
    )
    assert code_rules_enforcer.is_config_file("lib/myconfig.py") is False, (
        "lib/myconfig.py — config appears only in the filename stem, must be False"
    )
    assert code_rules_enforcer.is_config_file("src/app_config.py") is False, (
        "src/app_config.py — config appears only in the filename stem, must be False"
    )


def test_is_config_file_via_path_utils_returns_same_results_as_enforcer() -> None:
    """is_config_file from code_rules_path_utils must agree with the enforcer on all sample paths."""
    all_sample_paths = [
        "scripts/db/config.py",
        "config/timing.py",
        "settings.py",
    ]
    for each_path in all_sample_paths:
        enforcer_result = code_rules_enforcer.is_config_file(each_path)
        path_utils_result = path_utils_is_config_file(each_path)
        assert enforcer_result == path_utils_result, (
            f"is_config_file diverged for {each_path!r}: "
            f"enforcer={enforcer_result}, code_rules_path_utils={path_utils_result}"
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


def test_advisory_cap_matches_max_issues_per_check_constant() -> None:
    many_constants_source = (
        "def crowded_function():\n"
        "    ALPHA_CONSTANT = 1\n"
        "    BETA_CONSTANT = 2\n"
        "    GAMMA_CONSTANT = 3\n"
        "    DELTA_CONSTANT = 4\n"
        "    EPSILON_CONSTANT = 5\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        many_constants_source,
        "example_module.py",
    )
    assert len(advisory_issues) == code_rules_enforcer.MAX_ISSUES_PER_CHECK, (
        "Advisory cap must equal MAX_ISSUES_PER_CHECK, not a hardcoded literal"
    )


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
