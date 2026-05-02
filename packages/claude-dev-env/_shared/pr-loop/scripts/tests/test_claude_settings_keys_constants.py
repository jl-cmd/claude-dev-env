"""Tests for claude_settings_keys_constants.py extracted constant set."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = (
        Path(__file__).parent.parent / "config" / "claude_settings_keys_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "config.claude_settings_keys_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_permissions_key_is_typed_string() -> None:
    assert isinstance(constants_module.CLAUDE_SETTINGS_PERMISSIONS_KEY, str)
    assert constants_module.CLAUDE_SETTINGS_PERMISSIONS_KEY == "permissions"


def test_allow_key_is_typed_string() -> None:
    assert isinstance(constants_module.CLAUDE_SETTINGS_ALLOW_KEY, str)
    assert constants_module.CLAUDE_SETTINGS_ALLOW_KEY == "allow"


def test_additional_directories_key_is_typed_string() -> None:
    assert isinstance(constants_module.CLAUDE_SETTINGS_ADDITIONAL_DIRECTORIES_KEY, str)
    assert (
        constants_module.CLAUDE_SETTINGS_ADDITIONAL_DIRECTORIES_KEY
        == "additionalDirectories"
    )


def test_auto_mode_key_is_typed_string() -> None:
    assert isinstance(constants_module.CLAUDE_SETTINGS_AUTO_MODE_KEY, str)
    assert constants_module.CLAUDE_SETTINGS_AUTO_MODE_KEY == "autoMode"


def test_environment_key_is_typed_string() -> None:
    assert isinstance(constants_module.CLAUDE_SETTINGS_ENVIRONMENT_KEY, str)
    assert constants_module.CLAUDE_SETTINGS_ENVIRONMENT_KEY == "environment"
