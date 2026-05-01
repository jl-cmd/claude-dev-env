"""Tests for directory-anchored config path detection and function-local UPPER_SNAKE scanning.

Covers:
- is_config_file: must use directory-segment matching, not filename-stem matching
- check_constants_outside_config: advisory (not blocking) for function-body UPPER_SNAKE
- check_constants_outside_config: stable sort order by line number
"""

from __future__ import annotations

import importlib.util
import io
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

PRODUCTION_FILE_PATH = "packages/claude-dev-env/src/example.py"


def test_should_return_false_for_filename_named_config_dot_py() -> None:
    assert code_rules_enforcer.is_config_file("scripts/db/config.py") is False


def test_should_return_true_for_file_inside_config_directory_forward_slash() -> None:
    assert code_rules_enforcer.is_config_file("config/timing.py") is True


def test_should_return_true_for_file_inside_nested_config_directory() -> None:
    assert code_rules_enforcer.is_config_file("my_project/config/constants.py") is True


def test_should_return_true_for_settings_dot_py() -> None:
    assert code_rules_enforcer.is_config_file("settings.py") is True


def test_should_return_false_for_subconfig_in_non_config_dir() -> None:
    assert code_rules_enforcer.is_config_file("src/subconfiguration.py") is False


def test_should_return_false_for_config_in_filename_not_directory() -> None:
    assert code_rules_enforcer.is_config_file("src/app_config.py") is False


def test_should_return_true_for_config_dir_backslash() -> None:
    assert code_rules_enforcer.is_config_file("project\\config\\constants.py") is True


def test_should_produce_advisory_not_blocking_for_function_local_upper_snake() -> None:
    source = (
        "def fetch_data():\n"
        "    MAX_RETRIES = 3\n"
        "    for attempt in range(MAX_RETRIES):\n"
        "        pass\n"
    )
    advisory_issues = code_rules_enforcer.check_constants_outside_config_advisory(
        source, PRODUCTION_FILE_PATH
    )
    blocking_issues = code_rules_enforcer.check_constants_outside_config(
        source, PRODUCTION_FILE_PATH
    )
    assert any("MAX_RETRIES" in issue for issue in advisory_issues)
    assert not any("MAX_RETRIES" in issue for issue in blocking_issues)


def test_should_produce_blocking_for_module_level_upper_snake_outside_config() -> None:
    source = "MAX_RETRIES = 3\n\ndef fetch_data():\n    pass\n"
    blocking_issues = code_rules_enforcer.check_constants_outside_config(
        source, PRODUCTION_FILE_PATH
    )
    assert any("MAX_RETRIES" in issue for issue in blocking_issues)


def test_should_produce_stable_ordering_sorted_by_line_number() -> None:
    source = (
        "ALPHA_CONSTANT = 1\n"
        "BETA_CONSTANT = 2\n"
        "GAMMA_CONSTANT = 3\n"
        "\n"
        "def placeholder():\n"
        "    pass\n"
    )
    issues = code_rules_enforcer.check_constants_outside_config(
        source, PRODUCTION_FILE_PATH
    )
    line_numbers = []
    for each_issue in issues:
        parts = each_issue.split(":")
        if parts[0].startswith("Line "):
            line_numbers.append(int(parts[0].replace("Line ", "").strip()))
    assert line_numbers == sorted(line_numbers)
