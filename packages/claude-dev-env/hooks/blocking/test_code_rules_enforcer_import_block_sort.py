"""Tests for the ruff-I001 import-block-sort gate in code_rules_imports_logging.

The gate delegates to ruff itself, so these tests run real ruff over real source
shapes (the same way the repo quality gate does) rather than mocking the
subprocess. A sorted block passes; the PR #749 shape — two local ``from`` imports
out of alphabetical order in one contiguous block — fails with an I001 issue.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

IMPORTS_MODULE_FILENAME = "code_rules_imports_logging.py"
IMPORTS_MODULE_NAME = "code_rules_imports_logging_under_test"
PRODUCTION_PYTHON_TARGET = str(Path(__file__).parent / "production_module.py")

SORTED_IMPORT_BLOCK_SOURCE = (
    "import json\n"
    "import os\n"
    "\n"
    "from package.alpha import first\n"
    "from package.beta import second\n"
    "from package.gamma import third\n"
)

UNSORTED_IMPORT_BLOCK_SOURCE = (
    "import json\n"
    "import os\n"
    "\n"
    "from package.gamma import third\n"
    "from package.alpha import first\n"
    "from package.beta import second\n"
)


def load_imports_module() -> ModuleType:
    module_path = Path(__file__).parent / IMPORTS_MODULE_FILENAME
    module_spec = importlib.util.spec_from_file_location(IMPORTS_MODULE_NAME, module_path)
    assert module_spec is not None
    assert module_spec.loader is not None
    imports_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(imports_module)
    return imports_module


imports_logging = load_imports_module()


def test_should_flag_unsorted_import_block() -> None:
    issues = imports_logging.check_import_block_sorted(
        UNSORTED_IMPORT_BLOCK_SOURCE, PRODUCTION_PYTHON_TARGET
    )
    assert len(issues) == 1
    assert "un-sorted (ruff I001)" in issues[0]


def test_should_allow_sorted_import_block() -> None:
    issues = imports_logging.check_import_block_sorted(
        SORTED_IMPORT_BLOCK_SOURCE, PRODUCTION_PYTHON_TARGET
    )
    assert issues == []


def test_should_report_the_block_anchor_line_number() -> None:
    issues = imports_logging.check_import_block_sorted(
        UNSORTED_IMPORT_BLOCK_SOURCE, PRODUCTION_PYTHON_TARGET
    )
    assert issues[0].startswith("Line 1:")


def test_should_exempt_test_files() -> None:
    issues = imports_logging.check_import_block_sorted(
        UNSORTED_IMPORT_BLOCK_SOURCE, "test_something.py"
    )
    assert issues == []


def test_should_exempt_non_python_files() -> None:
    issues = imports_logging.check_import_block_sorted(UNSORTED_IMPORT_BLOCK_SOURCE, "notes.md")
    assert issues == []


def test_should_fail_open_on_unparseable_source() -> None:
    broken_source = "def (:::\n   import os\n"
    issues = imports_logging.check_import_block_sorted(broken_source, PRODUCTION_PYTHON_TARGET)
    assert issues == []


def test_should_fail_open_when_no_ruff_config_is_discoverable(tmp_path: Path) -> None:
    target_without_config = tmp_path / "standalone_module.py"
    issues = imports_logging.check_import_block_sorted(
        UNSORTED_IMPORT_BLOCK_SOURCE, str(target_without_config)
    )
    assert issues == []
