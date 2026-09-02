"""Tests for directory-anchored config path detection and function-local UPPER_SNAKE scanning.

Covers:
- is_config_file: must use directory-segment matching, not filename-stem matching
- check_constants_outside_config: advisory (not blocking) for function-body UPPER_SNAKE
- check_constants_outside_config: stable sort order by line number
"""

from __future__ import annotations

import importlib.util
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
    check_constants_outside_config,
    check_constants_outside_config_advisory,
)
from code_rules_path_utils import is_config_file  # noqa: E402

code_rules_enforcer = SimpleNamespace(
    check_constants_outside_config=check_constants_outside_config,
    check_constants_outside_config_advisory=check_constants_outside_config_advisory,
    is_config_file=is_config_file,
)

_enforcer_module_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer_under_test", Path(_BLOCKING_DIRECTORY) / "code_rules_enforcer.py"
)
assert _enforcer_module_spec is not None
assert _enforcer_module_spec.loader is not None
code_rules_enforcer_module = importlib.util.module_from_spec(_enforcer_module_spec)
_enforcer_module_spec.loader.exec_module(code_rules_enforcer_module)

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
    blocking_issues = code_rules_enforcer.check_constants_outside_config(
        source, PRODUCTION_FILE_PATH
    )
    assert not any("MAX_RETRIES" in issue for issue in blocking_issues)


def test_function_local_upper_snake_advisory_never_reaches_the_deny_payload() -> None:
    source = (
        "def fetch_data():\n"
        "    MAX_RETRIES = 3\n"
        "    for attempt in range(MAX_RETRIES):\n"
        "        pass\n"
    )
    edit_lane_issues = code_rules_enforcer_module.validate_content_for_edit_lane(
        source, PRODUCTION_FILE_PATH
    )
    assert not any("MAX_RETRIES" in issue for issue in edit_lane_issues), (
        f"Expected function-local MAX_RETRIES to stay out of the deny payload, "
        f"got: {edit_lane_issues}"
    )


def test_should_produce_blocking_for_module_level_upper_snake_outside_config() -> None:
    source = "MAX_RETRIES = 3\n\ndef fetch_data():\n    pass\n"
    blocking_issues = code_rules_enforcer.check_constants_outside_config(
        source, PRODUCTION_FILE_PATH
    )
    assert any("MAX_RETRIES" in issue for issue in blocking_issues)


def test_module_level_upper_snake_still_reaches_the_deny_payload() -> None:
    source = "MAXIMUM_RETRIES = 3\n\ndef fetch_data() -> int:\n    return MAXIMUM_RETRIES\n"
    edit_lane_issues = code_rules_enforcer_module.validate_content_for_edit_lane(
        source, PRODUCTION_FILE_PATH
    )
    assert any(
        "MAXIMUM_RETRIES" in issue and "move to config/" in issue
        for issue in edit_lane_issues
    ), f"Expected module-level MAXIMUM_RETRIES to keep denying the write, got: {edit_lane_issues}"


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
