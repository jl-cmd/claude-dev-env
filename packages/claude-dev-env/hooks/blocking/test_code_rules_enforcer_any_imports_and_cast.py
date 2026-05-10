"""Tests for `from typing import Any` and `cast()` detection in production.

CODE_RULES.md §6 (no `Any`) and Plan Phase 1a require:
- `from typing import Any` (and re-export forms) flagged in production
- `from typing import *` flagged (introduces Any access)
- `cast()` calls flagged in production
- Test files exempt; hook infrastructure exempt
"""

from __future__ import annotations

import importlib.util
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
check_type_escape_hatches = code_rules_enforcer.check_type_escape_hatches

PRODUCTION_FILE_PATH = "/project/src/module.py"
TEST_FILE_PATH = "/project/src/test_module.py"


def test_should_flag_from_typing_import_any() -> None:
    source = "from typing import Any\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any(
        "Any" in each_issue and "import" in each_issue.lower() for each_issue in issues
    ), f"Expected 'from typing import Any' to be flagged, got: {issues!r}"


def test_should_flag_from_typing_import_any_among_others() -> None:
    source = "from typing import Optional, Any, Dict\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any(
        "Any" in each_issue and "import" in each_issue.lower() for each_issue in issues
    ), f"Expected 'Any' inside multi-import to be flagged, got: {issues!r}"


def test_should_not_flag_from_typing_import_without_any() -> None:
    source = "from typing import Optional, Dict, List\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Expected no issues for typing import without Any, got: {issues!r}"
    )


def test_should_flag_from_typing_import_star() -> None:
    source = "from typing import *\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any(
        "import *" in each_issue or "wildcard" in each_issue.lower()
        for each_issue in issues
    ), f"Expected 'from typing import *' to be flagged, got: {issues!r}"


def test_should_flag_cast_call_in_production() -> None:
    source = "from typing import cast\n\nx = cast(str, value)\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("cast" in each_issue for each_issue in issues), (
        f"Expected cast() call to be flagged, got: {issues!r}"
    )


def test_should_flag_typing_cast_call() -> None:
    source = "import typing\n\nx = typing.cast(int, value)\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("cast" in each_issue for each_issue in issues), (
        f"Expected typing.cast() call to be flagged, got: {issues!r}"
    )


def test_should_not_flag_cast_in_test_file() -> None:
    source = "from typing import cast\nx = cast(str, value)\n"
    issues = check_type_escape_hatches(source, TEST_FILE_PATH)
    assert issues == [], f"Test files must be exempt, got: {issues!r}"


def test_should_not_flag_typing_import_any_in_test_file() -> None:
    source = "from typing import Any\nx: Any = 1\n"
    issues = check_type_escape_hatches(source, TEST_FILE_PATH)
    assert issues == [], f"Test files must be exempt, got: {issues!r}"
