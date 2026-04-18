"""Tests for file-global constants use-count rule (jl-cmd/claude-code-config#180).

A module-level UPPER_SNAKE constant must be referenced by at least two
distinct functions/methods. A constant referenced by only one function
belongs in that function's scope. Constants with zero function references
are out of this rule's concern. Test files are exempt.
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


PRODUCTION_FILE_PATH = "packages/claude-dev-env/hooks/blocking/example_production.py"
TEST_FILE_PATH = "packages/claude-dev-env/hooks/blocking/test_example.py"
TYPESCRIPT_FILE_PATH = "packages/claude-dev-env/hooks/blocking/example.ts"


def test_should_flag_constant_used_by_only_one_function() -> None:
    source = "UPPER = 1\n\ndef lonely_caller():\n    return UPPER\n"
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert any(
        "UPPER" in issue and "only 1 function/method" in issue for issue in issues
    ), f"Expected single-caller violation for UPPER, got: {issues}"


def test_should_accept_constant_used_by_two_functions() -> None:
    source = (
        "UPPER = 1\n"
        "\n"
        "def first_caller():\n"
        "    return UPPER\n"
        "\n"
        "def second_caller():\n"
        "    return UPPER + 1\n"
    )
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Expected no violation for 2 callers, got: {issues}"


def test_should_accept_constant_used_by_method_and_function() -> None:
    source = (
        "UPPER = 1\n"
        "\n"
        "class Holder:\n"
        "    def show(self):\n"
        "        return UPPER\n"
        "\n"
        "def also_uses():\n"
        "    return UPPER\n"
    )
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Expected no violation for method + function, got: {issues}"


def test_should_accept_constant_used_by_two_methods_of_same_class() -> None:
    source = (
        "UPPER = 1\n"
        "\n"
        "class Holder:\n"
        "    def method_a(self):\n"
        "        return UPPER\n"
        "\n"
        "    def method_b(self):\n"
        "        return UPPER + 1\n"
    )
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Expected no violation for two methods same class, got: {issues}"
    )


def test_should_accept_constant_with_zero_function_references() -> None:
    source = "UPPER = 1\n\ndef unrelated():\n    return 0\n"
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Expected no violation for zero-reference constant, got: {issues}"
    )


def test_should_exempt_test_files() -> None:
    source = "UPPER = 1\n\ndef lonely_caller():\n    return UPPER\n"
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, TEST_FILE_PATH
    )
    assert issues == [], f"Expected test file exemption, got: {issues}"


def test_should_flag_constant_used_only_in_decorator_of_one_function() -> None:
    source = (
        "TIMEOUT = 5.0\n"
        "\n"
        "def cache(seconds):\n"
        "    def wrap(function):\n"
        "        return function\n"
        "    return wrap\n"
        "\n"
        "@cache(TIMEOUT)\n"
        "def fetch_data():\n"
        "    return 0\n"
    )
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert any(
        "TIMEOUT" in issue and "only 1 function/method" in issue for issue in issues
    ), f"Expected decorator usage to count as single caller, got: {issues}"


def test_should_flag_ann_assign_constant_used_by_only_one_function() -> None:
    source = (
        "from typing import Final\n"
        "\n"
        "TIMEOUT: Final[int] = 5\n"
        "\n"
        "def lonely_caller():\n"
        "    return TIMEOUT\n"
    )
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert any(
        "TIMEOUT" in issue and "only 1 function/method" in issue for issue in issues
    ), f"Expected AnnAssign constant to be flagged, got: {issues}"


def test_should_flag_private_upper_snake_constant_used_by_only_one_function() -> None:
    source = (
        '_PRIVATE_CONSTANT = "x"\n'
        "\n"
        "def lonely_caller():\n"
        "    return _PRIVATE_CONSTANT\n"
    )
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert any(
        "_PRIVATE_CONSTANT" in issue and "only 1 function/method" in issue
        for issue in issues
    ), f"Expected private UPPER_SNAKE to be flagged, got: {issues}"


def test_should_accept_constant_referenced_only_at_module_scope() -> None:
    source = "A = 1\nB = A + 1\n"
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Expected module-scope reference to not count, got: {issues}"


def test_should_skip_non_python_files() -> None:
    source = "const UPPER = 1;\nfunction lonelyCaller() { return UPPER; }\n"
    issues = code_rules_enforcer.check_file_global_constants_use_count(
        source, TYPESCRIPT_FILE_PATH
    )
    assert issues == [], f"Expected TypeScript file to be skipped, got: {issues}"
