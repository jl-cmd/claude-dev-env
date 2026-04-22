"""Tests for the shared path-classification helper extracted to code_rules_path_utils.

Finding A: is_config_file was duplicated between code_rules_enforcer.py and
exempt_paths.py. The canonical implementation now lives in code_rules_path_utils.py;
both files import from here.

These tests verify the directory-segment matching semantics: only files whose
parent directory is named 'config', or whose filename is settings.py, match.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BLOCKING_DIR = Path(__file__).resolve().parent
if str(_BLOCKING_DIR) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIR))

from code_rules_path_utils import is_config_file  # noqa: E402


def test_should_return_false_for_scripts_db_config_py() -> None:
    assert is_config_file("scripts/db/config.py") is False


def test_should_return_false_for_lib_myconfig_py() -> None:
    assert is_config_file("lib/myconfig.py") is False


def test_should_return_true_for_config_timing_py() -> None:
    assert is_config_file("config/timing.py") is True


def test_should_return_true_for_nested_config_dir() -> None:
    assert is_config_file("packages/myapp/config/constants.py") is True


def test_should_return_true_for_settings_py() -> None:
    assert is_config_file("settings.py") is True


def test_should_return_true_for_settings_py_with_prefix() -> None:
    assert is_config_file("any/path/settings.py") is True


def test_should_return_false_for_mysettings_py() -> None:
    assert is_config_file("mysettings.py") is False


def test_should_return_true_for_backslash_config_path() -> None:
    assert is_config_file("packages\\myapp\\config\\timing.py") is True
