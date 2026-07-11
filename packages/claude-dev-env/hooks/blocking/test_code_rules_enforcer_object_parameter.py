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
check_loop_variable_naming = code_rules_enforcer.check_loop_variable_naming

PRODUCTION_FILE_PATH = "/project/src/module.py"
TEST_FILE_PATH = "/project/src/test_module.py"
TYPE_ESCAPE_MODULE_PATH = Path(__file__).parent / "code_rules_type_escape.py"


def test_type_escape_module_has_no_collection_prefix_violations() -> None:
    source = TYPE_ESCAPE_MODULE_PATH.read_text(encoding="utf-8")
    issues = check_collection_prefix(source, str(TYPE_ESCAPE_MODULE_PATH))
    assert issues == [], f"Collection-parameter naming must be clean, got: {issues!r}"


def test_type_escape_module_has_no_loop_variable_naming_violations() -> None:
    source = TYPE_ESCAPE_MODULE_PATH.read_text(encoding="utf-8")
    issues = check_loop_variable_naming(source, str(TYPE_ESCAPE_MODULE_PATH))
    assert issues == [], f"Loop-variable naming must be clean, got: {issues!r}"


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


def test_should_flag_object_parameter_dereferenced_inside_nested_class_method() -> None:
    source = (
        "def outer(node: object) -> object:\n"
        "    class Inner:\n"
        "        def m(self) -> None:\n"
        "            print(node.text)\n"
        "    return Inner\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"A class-nested method reads the outer object parameter from the enclosing scope; "
        f"that dereference must be flagged, got: {issues!r}"
    )


def test_should_flag_earlier_object_deref_when_later_comprehension_reuses_name() -> None:
    source = (
        "def f(node: object) -> list:\n"
        "    node.run()\n"
        "    return [node for node in items()]\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"A genuine top-level dereference before a later comprehension reuses the name must stay flagged, "
        f"got: {issues!r}"
    )


def test_should_flag_top_level_object_deref_when_nested_function_reuses_name() -> None:
    source = (
        "def outer(node: object) -> None:\n"
        "    print(node.text)\n"
        "    def inner(node: int) -> None:\n"
        "        pass\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"A top-level dereference must stay flagged even when a nested function reuses the name, got: {issues!r}"
    )


def test_should_flag_top_level_object_deref_when_lambda_reuses_name() -> None:
    source = (
        "def outer(node: object) -> object:\n"
        "    print(node.text)\n"
        "    return lambda node: node.text\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"A top-level dereference must stay flagged even when a lambda reuses the name, got: {issues!r}"
    )


def test_should_flag_both_object_parameters_when_one_name_collides_with_comprehension_target() -> None:
    source = (
        "def f(a: object, b: object) -> None:\n"
        "    print(a.x)\n"
        "    print(b.y)\n"
        "    all_squares = [a for a in range(3)]\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "'a'" in each_issue for each_issue in issues), (
        f"Top-level a.x must be flagged even though a comprehension reuses 'a', got: {issues!r}"
    )
    assert any("object" in each_issue and "'b'" in each_issue for each_issue in issues), (
        f"Top-level b.y must be flagged, got: {issues!r}"
    )


def test_should_flag_object_parameter_dereferenced_on_conditional_rebind_fall_through() -> None:
    source = (
        "def f(client: object, cond: bool) -> None:\n"
        "    if cond:\n"
        "        client = wrap(client)\n"
        "    client.connect()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "client" in each_issue for each_issue in issues), (
        f"A conditional rebind does not dominate the fall-through dereference, so client.connect() "
        f"must stay flagged, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_rebound_then_dereferenced_in_same_branch() -> None:
    source = (
        "def f(client: object, cond: bool) -> None:\n"
        "    if cond:\n"
        "        client = wrap(client)\n"
        "        client.connect()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A rebind that dominates the read within the same branch suppresses the dereference, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_rebound_by_for_loop_target() -> None:
    source = (
        "def f(node: object) -> None:\n"
        "    for node in items():\n"
        "        node.run()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A for-loop target rebinds node to the loop element; the body read targets the element, "
        f"not the object parameter, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_rebound_by_with_as_target() -> None:
    source = (
        "def f(node: object) -> str:\n"
        "    with open_ctx() as node:\n"
        "        return node.read()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A with-as target rebinds node to the context object; the body read targets the context "
        f"object, not the object parameter, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_rebound_by_walrus_in_if_test() -> None:
    source = (
        "def f(node: object) -> str:\n"
        "    if (node := wrap(node)):\n"
        "        return node.text\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A walrus rebind in the if test rebinds node to the wrap() result; the body read targets "
        f"that result, not the object parameter, got: {issues!r}"
    )


def test_should_still_flag_object_parameter_dereferenced_in_loop_without_rebind() -> None:
    source = (
        "def f(node: object) -> None:\n"
        "    while True:\n"
        "        node.run()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"A loop body that dereferences the object parameter without rebinding it must stay flagged, "
        f"got: {issues!r}"
    )


def test_should_not_flag_object_parameter_rebound_by_except_handler_name() -> None:
    source = (
        "def f(node: object) -> None:\n"
        "    try:\n"
        "        go()\n"
        "    except E as node:\n"
        "        node.run()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"An 'except E as node' clause rebinds node to the caught exception; the handler-body read "
        f"targets the exception, not the object parameter, got: {issues!r}"
    )


def test_should_still_flag_object_parameter_read_in_other_handler_without_rebind() -> None:
    source = (
        "def f(node: object) -> None:\n"
        "    try:\n"
        "        go()\n"
        "    except E as node:\n"
        "        node.run()\n"
        "    except OtherError:\n"
        "        node.fail()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"A read in a sibling handler that does not rebind node must stay flagged even when another "
        f"handler binds node, got: {issues!r}"
    )


def test_should_still_flag_object_parameter_read_in_handler_without_as_binding() -> None:
    source = (
        "def f(node: object) -> None:\n"
        "    try:\n"
        "        go()\n"
        "    except E:\n"
        "        node.run()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"An 'except E' clause without an 'as' binding leaves node bound to the object parameter, so "
        f"the handler-body read must stay flagged, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_rebound_by_match_case_capture() -> None:
    source = (
        "def f(node: object) -> None:\n"
        "    match get():\n"
        "        case node:\n"
        "            node.run()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A 'case node' capture pattern rebinds node to the matched subject; the case-body read "
        f"targets that subject, not the object parameter, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_rebound_by_match_as_subpattern() -> None:
    source = (
        "def f(node: object) -> None:\n"
        "    match get():\n"
        "        case Point(x=0) as node:\n"
        "            node.run()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A 'case ... as node' pattern rebinds node to the matched value; the case-body read targets "
        f"that value, not the object parameter, got: {issues!r}"
    )


def test_should_still_flag_object_parameter_read_in_sibling_case_without_capture() -> None:
    source = (
        "def f(node: object) -> None:\n"
        "    match get():\n"
        "        case node:\n"
        "            node.run()\n"
        "        case 0:\n"
        "            node.fail()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "node" in each_issue for each_issue in issues), (
        f"A read in a sibling case that does not capture node must stay flagged even when another "
        f"case captures node, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_narrowed_by_isinstance_guard() -> None:
    source = (
        "def f(value: object) -> None:\n"
        "    if isinstance(value, Foo):\n"
        "        value.bar()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"An isinstance(value, Foo) guard narrows value to Foo; the guarded read is type-checked, "
        f"got: {issues!r}"
    )


def test_should_not_flag_eq_dunder_isinstance_narrowed_other() -> None:
    source = (
        "def __eq__(self, other: object) -> bool:\n"
        "    if not isinstance(other, C):\n"
        "        return NotImplemented\n"
        "    return other.value == self.value\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"The canonical __eq__ idiom narrows other via isinstance before reading other.value; that "
        f"read is type-checked, got: {issues!r}"
    )


def test_should_not_flag_object_parameter_narrowed_then_method_called() -> None:
    source = (
        "def g(convergence_summary: object) -> bool:\n"
        "    if not isinstance(convergence_summary, dict):\n"
        "        return False\n"
        "    return bool(convergence_summary.get('k'))\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"A negative isinstance early return narrows the parameter on the fall-through path; the "
        f"later read is type-checked, got: {issues!r}"
    )


def test_should_still_flag_object_parameter_dereferenced_without_isinstance_guard() -> None:
    source = "def g(value: object) -> None:\n    value.attr()\n"
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "value" in each_issue for each_issue in issues), (
        f"An unguarded dereference of an object parameter must still be flagged, got: {issues!r}"
    )


def test_should_still_flag_object_parameter_read_before_isinstance_guard() -> None:
    source = (
        "def f(value: object) -> None:\n"
        "    value.early()\n"
        "    if isinstance(value, Foo):\n"
        "        value.bar()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "value" in each_issue for each_issue in issues), (
        f"A read that precedes the isinstance guard is not narrowed and must stay flagged, got: {issues!r}"
    )


def test_should_still_flag_object_parameter_read_in_else_of_isinstance_guard() -> None:
    source = (
        "def f(value: object) -> None:\n"
        "    if isinstance(value, Foo):\n"
        "        return\n"
        "    value.attr()\n"
    )
    issues = check_type_escape_hatches(source, PRODUCTION_FILE_PATH)
    assert any("object" in each_issue and "value" in each_issue for each_issue in issues), (
        f"A positive isinstance guard does not narrow the fall-through path; the read after it must "
        f"stay flagged, got: {issues!r}"
    )
