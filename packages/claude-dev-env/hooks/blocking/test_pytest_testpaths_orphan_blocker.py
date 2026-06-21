"""Tests for pytest_testpaths_orphan_blocker hook."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pytest_testpaths_orphan_blocker import (
    _explicit_testpaths,
    _is_collected_by_entry,
    find_unregistered_test_directory,
    is_test_file,
)

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "pytest_testpaths_orphan_blocker.py")

PYPROJECT_WITH_EXPLICIT_TESTPATHS = (
    "[tool.pytest.ini_options]\n"
    'testpaths = [\n    "tests",\n    "samsung_utils/tests",\n]\n'
    'python_files = ["test_*.py"]\n'
)

PYPROJECT_WITH_NO_PYTEST_SECTION = '[build-system]\nrequires = ["setuptools"]\n'

PYPROJECT_WITH_EMPTY_TESTPATHS = "[tool.pytest.ini_options]\ntestpaths = []\n"

PYPROJECT_WITH_DOT_TESTPATHS = '[tool.pytest.ini_options]\ntestpaths = ["."]\n'

PYPROJECT_WITH_DOT_PREFIXED_TESTPATHS = '[tool.pytest.ini_options]\ntestpaths = ["./tests"]\n'

PYPROJECT_WITH_GLOB_TESTPATHS = '[tool.pytest.ini_options]\ntestpaths = ["tests/*"]\n'

PYPROJECT_WITH_SCALAR_TOOL = 'tool = "x"\n'

PYPROJECT_WITH_SCALAR_PYTEST = "[tool]\npytest = \"oops\"\n"

PYPROJECT_WITH_SCALAR_INI_OPTIONS = "[tool.pytest]\nini_options = \"oops\"\n"


def _write_package(package_root: Path, pyproject_text: str) -> None:
    """Write a pyproject.toml into *package_root*, creating the directory tree.

    Args:
        package_root: The directory that holds the package's pyproject.toml.
        pyproject_text: The pyproject content to write.
    """
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "pyproject.toml").write_text(pyproject_text, encoding="utf-8")


class _RunHook:
    """Helper to test the hook via subprocess, mirroring the sibling test style."""

    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )


_run_hook = _RunHook()


def test_is_test_file_accepts_test_prefixed_python_file() -> None:
    assert is_test_file("/repo/package/theme_assets/tests/test_palette.py") is True


def test_is_test_file_rejects_production_module() -> None:
    assert is_test_file("/repo/package/theme_assets/palette.py") is False


def test_find_flags_test_directory_absent_from_explicit_testpaths(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_EXPLICIT_TESTPATHS)
    unregistered_test_file = package_root / "theme_assets" / "tests" / "test_palette.py"
    block_details = find_unregistered_test_directory(str(unregistered_test_file))
    assert block_details is not None
    assert block_details["test_directory"] == "theme_assets/tests"
    assert block_details["suggested_entry"] == "theme_assets/tests"


def test_find_passes_test_directory_listed_in_testpaths(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_EXPLICIT_TESTPATHS)
    registered_test_file = package_root / "samsung_utils" / "tests" / "test_normalizer.py"
    assert find_unregistered_test_directory(str(registered_test_file)) is None


def test_find_passes_test_directory_named_tests_at_package_root(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_EXPLICIT_TESTPATHS)
    registered_test_file = package_root / "tests" / "test_root_behavior.py"
    assert find_unregistered_test_directory(str(registered_test_file)) is None


def test_find_passes_when_pyproject_has_no_pytest_section(tmp_path: Path) -> None:
    package_root = tmp_path / "loose_package"
    _write_package(package_root, PYPROJECT_WITH_NO_PYTEST_SECTION)
    any_test_file = package_root / "deep" / "nested" / "test_anything.py"
    assert find_unregistered_test_directory(str(any_test_file)) is None


def test_find_passes_when_testpaths_list_is_empty(tmp_path: Path) -> None:
    package_root = tmp_path / "loose_package"
    _write_package(package_root, PYPROJECT_WITH_EMPTY_TESTPATHS)
    any_test_file = package_root / "deep" / "test_anything.py"
    assert find_unregistered_test_directory(str(any_test_file)) is None


def test_find_passes_when_no_governing_pyproject_exists(tmp_path: Path) -> None:
    bare_test_file = tmp_path / "no_package_here" / "test_orphan.py"
    assert find_unregistered_test_directory(str(bare_test_file)) is None


def test_hook_blocks_create_of_unregistered_test_file(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_EXPLICIT_TESTPATHS)
    unregistered_test_file = package_root / "theme_assets" / "tests" / "test_palette.py"
    completed = _run_hook(
        "Write",
        {
            "file_path": str(unregistered_test_file),
            "content": "def test_x() -> None:\n    assert True\n",
        },
    )
    decision = json.loads(completed.stdout)
    hook_output = decision["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert "theme_assets/tests" in hook_output["permissionDecisionReason"]


def test_hook_allows_create_of_registered_test_file(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_EXPLICIT_TESTPATHS)
    registered_test_file = package_root / "tests" / "test_root_behavior.py"
    completed = _run_hook(
        "Write",
        {
            "file_path": str(registered_test_file),
            "content": "def test_x() -> None:\n    assert True\n",
        },
    )
    assert completed.stdout.strip() == ""


def test_hook_ignores_edit_of_existing_test_file(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_EXPLICIT_TESTPATHS)
    existing_test_file = package_root / "theme_assets" / "tests" / "test_palette.py"
    existing_test_file.parent.mkdir(parents=True, exist_ok=True)
    existing_test_file.write_text("def test_old() -> None:\n    assert True\n", encoding="utf-8")
    completed = _run_hook(
        "Edit",
        {
            "file_path": str(existing_test_file),
            "old_string": "assert True",
            "new_string": "assert 1 == 1",
        },
    )
    assert completed.stdout.strip() == ""


def test_hook_ignores_non_test_python_file(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_EXPLICIT_TESTPATHS)
    production_module = package_root / "theme_assets" / "palette.py"
    completed = _run_hook(
        "Write",
        {"file_path": str(production_module), "content": "VALUE = 1\n"},
    )
    assert completed.stdout.strip() == ""


def test_find_passes_when_testpaths_is_dot_for_nested_file(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_DOT_TESTPATHS)
    nested_test_file = package_root / "theme_assets" / "tests" / "test_palette.py"
    assert find_unregistered_test_directory(str(nested_test_file)) is None


def test_find_passes_when_testpaths_is_dot_for_root_file(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_DOT_TESTPATHS)
    root_test_file = package_root / "test_root_behavior.py"
    assert find_unregistered_test_directory(str(root_test_file)) is None


def test_find_passes_when_testpaths_entry_has_dot_slash_prefix(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_DOT_PREFIXED_TESTPATHS)
    registered_test_file = package_root / "tests" / "test_root_behavior.py"
    assert find_unregistered_test_directory(str(registered_test_file)) is None


def test_find_passes_when_testpaths_entry_is_glob(tmp_path: Path) -> None:
    package_root = tmp_path / "shared_utils"
    _write_package(package_root, PYPROJECT_WITH_GLOB_TESTPATHS)
    registered_test_file = package_root / "tests" / "test_x.py"
    assert find_unregistered_test_directory(str(registered_test_file)) is None


def test_is_collected_by_entry_treats_dot_as_package_root() -> None:
    assert _is_collected_by_entry(Path("theme_assets/tests/test_palette.py"), ".") is True


def test_is_collected_by_entry_matches_glob_segment() -> None:
    assert _is_collected_by_entry(Path("tests/test_x.py"), "tests/*") is True


def test_explicit_testpaths_returns_none_for_scalar_tool(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(PYPROJECT_WITH_SCALAR_TOOL, encoding="utf-8")
    assert _explicit_testpaths(pyproject_path) is None


def test_explicit_testpaths_returns_none_for_scalar_pytest(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(PYPROJECT_WITH_SCALAR_PYTEST, encoding="utf-8")
    assert _explicit_testpaths(pyproject_path) is None


def test_explicit_testpaths_returns_none_for_scalar_ini_options(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(PYPROJECT_WITH_SCALAR_INI_OPTIONS, encoding="utf-8")
    assert _explicit_testpaths(pyproject_path) is None


def test_hook_does_not_crash_on_scalar_tool_ancestor(tmp_path: Path) -> None:
    package_root = tmp_path / "scalar_package"
    _write_package(package_root, PYPROJECT_WITH_SCALAR_TOOL)
    any_test_file = package_root / "deep" / "test_anything.py"
    completed = _run_hook(
        "Write",
        {
            "file_path": str(any_test_file),
            "content": "def test_x() -> None:\n    assert True\n",
        },
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == ""
