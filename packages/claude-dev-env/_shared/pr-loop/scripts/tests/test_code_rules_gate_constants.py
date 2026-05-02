"""Tests for code_rules_gate_constants.py extracted constant set."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = (
        Path(__file__).parent.parent / "config" / "code_rules_gate_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "config.code_rules_gate_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_max_violations_per_check_is_typed_integer() -> None:
    assert isinstance(constants_module.MAX_VIOLATIONS_PER_CHECK, int)
    assert constants_module.MAX_VIOLATIONS_PER_CHECK == 3


def test_expected_tuple_pair_length_is_typed_integer() -> None:
    assert isinstance(constants_module.EXPECTED_TUPLE_PAIR_LENGTH, int)
    assert constants_module.EXPECTED_TUPLE_PAIR_LENGTH == 2


def test_all_code_file_extensions_is_frozenset() -> None:
    assert isinstance(constants_module.ALL_CODE_FILE_EXTENSIONS, frozenset)
    assert constants_module.ALL_CODE_FILE_EXTENSIONS == frozenset(
        {".py", ".js", ".ts", ".tsx", ".jsx"}
    )


def test_all_literal_keyword_exemptions_is_frozenset() -> None:
    assert isinstance(constants_module.ALL_LITERAL_KEYWORD_EXEMPTIONS, frozenset)
    assert constants_module.ALL_LITERAL_KEYWORD_EXEMPTIONS == frozenset(
        {"true", "false", "none", "null"}
    )


def test_config_path_segment() -> None:
    assert constants_module.CONFIG_PATH_SEGMENT == "/config/"


def test_tests_path_segment() -> None:
    assert constants_module.TESTS_PATH_SEGMENT == "/tests/"


def test_test_filename_suffixes_present() -> None:
    assert "_test.py" in constants_module.ALL_TEST_FILENAME_SUFFIXES


def test_test_filename_glob_suffixes_present() -> None:
    assert ".test." in constants_module.ALL_TEST_FILENAME_GLOB_SUFFIXES
    assert ".spec." in constants_module.ALL_TEST_FILENAME_GLOB_SUFFIXES


def test_test_conftest_filename() -> None:
    assert constants_module.TEST_CONFTEST_FILENAME == "conftest.py"


def test_test_filename_prefix() -> None:
    assert constants_module.TEST_FILENAME_PREFIX == "test_"


def test_minimum_column_name_length_after_first_char() -> None:
    assert constants_module.MINIMUM_COLUMN_NAME_LENGTH_AFTER_FIRST_CHAR == 2


def test_git_name_status_added_prefix() -> None:
    assert constants_module.GIT_NAME_STATUS_ADDED_PREFIX == "A"


def test_git_name_status_renamed_prefix() -> None:
    assert constants_module.GIT_NAME_STATUS_RENAMED_PREFIX == "R"


def test_expected_rename_column_count() -> None:
    assert constants_module.EXPECTED_RENAME_COLUMN_COUNT == 3


def test_column_key_pattern_template_renders_with_minimum_length() -> None:
    rendered_pattern = constants_module.COLUMN_KEY_PATTERN_TEMPLATE.format(
        minimum_length=constants_module.MINIMUM_COLUMN_NAME_LENGTH_AFTER_FIRST_CHAR
    )
    assert rendered_pattern == r"^[a-z][a-z0-9_]{2,}$"


def test_git_diff_name_only_null_terminated_command_prefix_includes_dash_z() -> None:
    command_prefix = (
        constants_module.ALL_GIT_DIFF_NAME_ONLY_NULL_TERMINATED_COMMAND_PREFIX
    )
    assert command_prefix == ("git", "diff", "--name-only", "-z")

