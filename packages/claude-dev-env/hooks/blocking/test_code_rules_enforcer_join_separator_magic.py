from __future__ import annotations

import importlib.util
from pathlib import Path

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location("code_rules_enforcer", ENFORCER_PATH)
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/foo.py"
TEST_FILE_PATH = "packages/app/tests/test_foo.py"
CONFIG_FILE_PATH = "packages/app/config/constants.py"


def test_should_flag_literal_delimiter_join_separator_in_function_body() -> None:
    source = (
        "def render(all_paths: list) -> str:\n"
        "    return ', '.join(str(each_path) for each_path in all_paths)\n"
    )
    issues = code_rules_enforcer.check_join_separator_string_magic(source, PRODUCTION_FILE_PATH)
    assert any("join" in each_issue for each_issue in issues), (
        f"Expected literal join separator flagged, got: {issues}"
    )


def test_should_not_flag_named_constant_join_separator() -> None:
    source = (
        "from config.constants import JOIN_DELIMITER\n"
        "\n"
        "def render(all_paths: list) -> str:\n"
        "    return JOIN_DELIMITER.join(all_paths)\n"
    )
    issues = code_rules_enforcer.check_join_separator_string_magic(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Named constant separator must pass, got: {issues}"


def test_should_not_flag_empty_string_join_concatenation() -> None:
    source = "def concatenate(all_parts: list) -> str:\n    return ''.join(all_parts)\n"
    issues = code_rules_enforcer.check_join_separator_string_magic(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Empty-string join concatenation is idiomatic and must pass, got: {issues}"
    )


def test_should_skip_join_separator_in_test_files() -> None:
    source = "def test_render() -> None:\n    assert ', '.join(['a', 'b']) == 'a, b'\n"
    issues = code_rules_enforcer.check_join_separator_string_magic(source, TEST_FILE_PATH)
    assert issues == [], f"Test files exempt, got: {issues}"


def test_should_skip_join_separator_in_config_files() -> None:
    source = "def build_message(all_names: list) -> str:\n    return ', '.join(all_names)\n"
    issues = code_rules_enforcer.check_join_separator_string_magic(source, CONFIG_FILE_PATH)
    assert issues == [], f"Config files exempt, got: {issues}"


def test_should_report_join_separator_line_number() -> None:
    source = (
        "def render(all_paths: list) -> str:\n"
        "    joined = '; '.join(all_paths)\n"
        "    return joined\n"
    )
    issues = code_rules_enforcer.check_join_separator_string_magic(source, PRODUCTION_FILE_PATH)
    assert any("Line 2" in each_issue for each_issue in issues), (
        f"Expected line 2 reported, got: {issues}"
    )
