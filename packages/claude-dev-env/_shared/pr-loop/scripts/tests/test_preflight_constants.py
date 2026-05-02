"""Tests for preflight_constants.py extracted constant set."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "config" / "preflight_constants.py"
    specification = importlib.util.spec_from_file_location(
        "config.preflight_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_bugteam_preflight_skip_env_var_name() -> None:
    assert (
        constants_module.BUGTEAM_PREFLIGHT_SKIP_ENV_VAR_NAME == "BUGTEAM_PREFLIGHT_SKIP"
    )


def test_bugteam_preflight_skip_enabled_value() -> None:
    assert constants_module.BUGTEAM_PREFLIGHT_SKIP_ENABLED_VALUE == "1"


def test_git_directory_name() -> None:
    assert constants_module.GIT_DIRECTORY_NAME == ".git"


def test_claude_directory_name() -> None:
    assert constants_module.CLAUDE_DIRECTORY_NAME == ".claude"


def test_venv_directory_name() -> None:
    assert constants_module.VENV_DIRECTORY_NAME == ".venv"


def test_pytest_ini_filename() -> None:
    assert constants_module.PYTEST_INI_FILENAME == "pytest.ini"


def test_pyproject_toml_filename() -> None:
    assert constants_module.PYPROJECT_TOML_FILENAME == "pyproject.toml"


def test_pytest_toml_table_prefix() -> None:
    assert constants_module.PYTEST_TOML_TABLE_PREFIX == "[tool.pytest"


def test_all_test_file_patterns_for_discovery() -> None:
    assert constants_module.ALL_TEST_FILE_PATTERNS_FOR_DISCOVERY == (
        "test_*.py",
        "*_test.py",
    )


def test_all_tests_directory_ignore_parts_includes_venv_marker() -> None:
    assert constants_module.VENV_DIRECTORY_NAME in (
        constants_module.ALL_TESTS_DIRECTORY_IGNORE_PARTS
    )


def test_all_repository_root_marker_filenames() -> None:
    assert constants_module.ALL_REPOSITORY_ROOT_MARKER_FILENAMES == (
        constants_module.GIT_DIRECTORY_NAME,
        constants_module.PYTEST_INI_FILENAME,
    )


def test_pytest_no_tests_collected_exit_code() -> None:
    assert constants_module.PYTEST_NO_TESTS_COLLECTED_EXIT_CODE == 5
