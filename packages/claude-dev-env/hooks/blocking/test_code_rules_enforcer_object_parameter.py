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
check_collection_prefix = code_rules_enforcer.check_collection_prefix

PRODUCTION_FILE_PATH = "/project/src/module.py"
TEST_FILE_PATH = "/project/src/test_module.py"
TYPE_ESCAPE_MODULE_PATH = Path(__file__).parent / "code_rules_type_escape.py"


def test_type_escape_module_has_no_collection_prefix_violations() -> None:
    source = TYPE_ESCAPE_MODULE_PATH.read_text(encoding="utf-8")
    issues = check_collection_prefix(source, str(TYPE_ESCAPE_MODULE_PATH))
    assert issues == [], f"Collection-parameter naming must be clean, got: {issues!r}"


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


def test_should_not_flag_object_vararg_with_tuple_method_access() -> None:
    source = "def f(*args: object) -> int:\n    return args.count(0)\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"*args: object binds to tuple[object, ...]; tuple method access is type-safe, got: {issues!r}"
    )


def test_should_not_flag_object_kwarg_with_dict_method_access() -> None:
    source = "def f(**kwargs: object) -> object:\n    return kwargs.get('x')\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"**kwargs: object binds to dict[str, object]; dict method access is type-safe, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_reassigned_before_dereference() -> None:
    source = "def render(node: object) -> str:\n    node = parse(node)\n    return node.text\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Dereference targets the reassigned concrete value, not the object parameter, got: {issues!r}"
    )


def test_should_not_flag_outer_object_parameter_when_nested_function_shadows_name() -> None:
    source = (
        "def outer(node: object) -> None:\n"
        "    register(node)\n"
        "    def inner(node: Widget) -> str:\n"
        "        return node.text\n"
        "    inner(make())\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Nested function rebinds node to a concrete type; outer object parameter is identity-only, got: {issues!r}"
    )


def test_should_still_flag_object_parameter_dereferenced_directly() -> None:
    source = "def f(client: object) -> None:\n    client.connect()\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "client" in each_issue for each_issue in issues), (
        f"Direct dereference of an object parameter must still be flagged, got: {issues!r}"
    )


def test_should_still_flag_object_parameter_dereferenced_before_later_rebind() -> None:
    source = "def f(client: object) -> None:\n    client.connect()\n    client = None\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "client" in each_issue for each_issue in issues), (
        f"Dereference on the object parameter before a later rebind must still be flagged, got: {issues!r}"
    )


def test_should_not_flag_outer_object_parameter_when_lambda_shadows_name() -> None:
    source = (
        "def outer(node: object) -> object:\n"
        "    register(node)\n"
        "    return lambda node: node.text\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Lambda rebinds node to its own parameter; outer object parameter is identity-only, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_shadowed_by_comprehension_target() -> None:
    source = (
        "def outer(node: object) -> list:\n"
        "    register(node)\n"
        "    return [\n"
        "        node.text\n"
        "        for node in items()\n"
        "    ]\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Comprehension rebinds node to its loop target; outer object parameter is identity-only, got: {issues!r}"
    )


def test_should_flag_object_parameter_dereferenced_inside_comprehension_body() -> None:
    source = "def f(node: object) -> list:\n    return [node.text for each_index in range(2)]\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"A genuine object-parameter dereference inside a comprehension body must be flagged, got: {issues!r}"
    )
