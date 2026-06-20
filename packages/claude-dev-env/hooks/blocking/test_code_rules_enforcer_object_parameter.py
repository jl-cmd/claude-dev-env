"""Tests for object-typed dereferenced parameter detection in production.

CODE_RULES.md §6 (complete type hints) requires concrete parameter types. A
parameter annotated as the bare builtin ``object`` whose body reads an attribute
on it is a type escape hatch in the same family as ``Any``: ``object`` declares
no attributes, so every ``param.attribute`` access goes unchecked. A parameter
typed ``object`` the body never dereferences is honest and not flagged.
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


def test_should_flag_self_object_with_attribute_access() -> None:
    source = (
        "async def _fill_basic_info(self: object) -> None:\n"
        "    assert self.automation.actions is not None\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "self" in each_issue for each_issue in issues), (
        f"Expected self: object with attribute access to be flagged, got: {issues!r}"
    )


def test_should_flag_object_parameter_other_than_self() -> None:
    source = "def render(node: object) -> str:\n    return node.text\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"Expected object-typed dereferenced parameter to be flagged, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_without_attribute_access() -> None:
    source = "def register(handler: object) -> list[object]:\n    return [handler]\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Identity-only object parameter must not be flagged, got: {issues!r}"


def test_should_not_flag_concrete_typed_parameter_with_attribute_access() -> None:
    source = "def fill(self: 'AppInfoProcessor') -> None:\n    self.automation.run()\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], f"Concrete-typed parameter must not be flagged, got: {issues!r}"


def test_should_not_flag_object_parameter_in_test_file() -> None:
    source = "def fill(self: object) -> None:\n    self.automation.run()\n"
    issues = check_type_escape_hatches(source, TEST_FILE_PATH)
    assert issues == [], f"Test files must be exempt, got: {issues!r}"


def test_should_flag_each_distinct_object_parameter() -> None:
    source = (
        "def first(self: object) -> None:\n"
        "    self.run()\n"
        "def second(node: object) -> str:\n"
        "    return node.text\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    flagged_lines = [each_issue for each_issue in issues if "object" in each_issue]
    assert len(flagged_lines) == 2, f"Expected both object parameters flagged, got: {issues!r}"
