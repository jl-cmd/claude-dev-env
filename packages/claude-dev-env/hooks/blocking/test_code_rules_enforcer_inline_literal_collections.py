from __future__ import annotations

from pathlib import Path
import importlib.util

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location(
    "code_rules_enforcer", ENFORCER_PATH
)
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/foo.py"
TEST_FILE_PATH = "packages/app/tests/test_foo.py"
CONFIG_FILE_PATH = "packages/app/config/constants.py"


def test_should_flag_set_literal_with_three_string_constants_in_function_body() -> None:
    source = (
        "def is_known(value: str) -> bool:\n"
        "    return value in {'true', 'false', 'none'}\n"
    )
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, PRODUCTION_FILE_PATH
    )
    assert len(issues) == 1, f"Expected 3-element set flagged, got: {issues}"


def test_should_flag_list_literal_with_five_string_constants_in_function_body() -> None:
    source = (
        "def is_code_path(suffix: str) -> bool:\n"
        "    return suffix in ['.py', '.js', '.ts', '.tsx', '.jsx']\n"
    )
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, PRODUCTION_FILE_PATH
    )
    assert len(issues) == 1, f"Expected 5-element list flagged, got: {issues}"


def test_should_not_flag_two_element_set_literal() -> None:
    source = "def is_binary(value: str) -> bool:\n    return value in {'on', 'off'}\n"
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"2-element literal must not be flagged, got: {issues}"


def test_should_not_flag_literal_with_variable_references() -> None:
    source = (
        "def consume(a: int, b: int, c: int, d: int) -> list[int]:\n"
        "    return [a, b, c, d]\n"
    )
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Variable-reference literal must not be flagged, got: {issues}"
    )


def test_should_not_flag_module_level_literal() -> None:
    source = "ALL_VALID_KEYS = {'true', 'false', 'none'}\n"
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"Module-level literal must not be flagged by inline-collection check, got: {issues}"
    )


def test_should_skip_in_test_files() -> None:
    source = (
        "def test_something() -> None:\n"
        "    keys = {'true', 'false', 'none'}\n"
        "    assert 'true' in keys\n"
    )
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, TEST_FILE_PATH
    )
    assert issues == [], f"Test files exempt, got: {issues}"


def test_should_skip_in_config_files() -> None:
    source = "def known_keys() -> set[str]:\n    return {'true', 'false', 'none'}\n"
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, CONFIG_FILE_PATH
    )
    assert issues == [], f"Config files exempt (they own such tables), got: {issues}"


def test_should_flag_multiple_inline_collections_in_same_function() -> None:
    source = (
        "def consume(value: str) -> bool:\n"
        "    return value in {'a', 'b', 'c'} or value in {'x', 'y', 'z'}\n"
    )
    issues = code_rules_enforcer.check_inline_literal_collections(
        source, PRODUCTION_FILE_PATH
    )
    assert len(issues) == 2, f"Expected 2 flagged literals, got: {issues}"
