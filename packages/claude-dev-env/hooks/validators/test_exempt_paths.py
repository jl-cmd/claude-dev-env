"""Tests for exempt_paths path-classification helpers.

Covers the is_config_file() contract: only files whose parent directory
segment is literally 'config' should match. A filename of 'config.py'
outside a config/ directory must NOT match.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BLOCKING_DIR = str(Path(__file__).resolve().parent.parent / "blocking")
if _BLOCKING_DIR not in sys.path:
    sys.path.insert(0, _BLOCKING_DIR)

from validators.exempt_paths import is_config_file  # noqa: E402
from code_rules_path_utils import is_config_file as path_utils_is_config_file  # noqa: E402


def test_should_exempt_file_inside_config_directory() -> None:
    assert is_config_file("project/config/constants.py") is True


def test_should_exempt_file_inside_nested_config_directory() -> None:
    assert is_config_file("packages/myapp/config/timing.py") is True


def test_should_not_exempt_file_named_config_dot_py_outside_config_dir() -> None:
    assert is_config_file("scripts/db/config.py") is False


def test_should_not_exempt_file_with_config_in_filename_only() -> None:
    assert is_config_file("src/app_config.py") is False


def test_should_not_exempt_file_with_config_in_parent_partial_match() -> None:
    assert is_config_file("src/reconfigured/constants.py") is False


def test_should_exempt_settings_py_by_filename() -> None:
    assert is_config_file("any/path/settings.py") is True


def test_should_exempt_windows_path_inside_config_directory() -> None:
    assert is_config_file("packages\\myapp\\config\\timing.py") is True


def test_should_not_exempt_filename_ending_with_settings_py_but_not_exactly_settings_py() -> None:
    assert is_config_file("mysettings.py") is False


def test_should_exempt_bare_settings_py_filename() -> None:
    assert is_config_file("settings.py") is True


def test_should_exempt_settings_py_in_nested_path() -> None:
    assert is_config_file("path/to/settings.py") is True


def test_is_config_file_is_identical_function_object_from_path_utils() -> None:
    """After refactor, exempt_paths.is_config_file must be the same object as path_utils."""
    assert is_config_file is path_utils_is_config_file, (
        "exempt_paths.is_config_file must be imported from code_rules_path_utils, not re-defined"
    )
