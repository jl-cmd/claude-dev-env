"""Incomplete-mock test-quality check and its scope-shadowing helpers."""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_shared import (  # noqa: E402
    is_test_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_BUILTIN_DICT_METHOD_NAMES,
)


def _collect_mock_dict_keys(assign_value: ast.expr) -> set[str] | None:
    """Return the string key set for a dict literal, or None if not a dict literal."""
    if not isinstance(assign_value, ast.Dict):
        return None
    key_names: set[str] = set()
    for each_key in assign_value.keys:
        if isinstance(each_key, ast.Constant) and isinstance(each_key.value, str):
            key_names.add(each_key.value)
    return key_names


def _target_binds_name(target_node: ast.AST, variable_name: str) -> bool:
    """Return True when an assignment target binds variable_name.

    Handles the recursive assignment target shapes Python permits:
    a bare ``Name``, a ``Tuple`` or ``List`` of targets (including
    nested ones), and a ``Starred`` wrapper around any of the above.
    """
    if isinstance(target_node, ast.Name):
        return target_node.id == variable_name
    if isinstance(target_node, (ast.Tuple, ast.List)):
        return any(_target_binds_name(each_element, variable_name) for each_element in target_node.elts)
    if isinstance(target_node, ast.Starred):
        return _target_binds_name(target_node.value, variable_name)
    return False


def _function_arguments_bind_name(
    arguments_node: ast.arguments,
    variable_name: str,
) -> bool:
    """Return True when any parameter slot declares variable_name."""
    all_positional_arguments = list(arguments_node.posonlyargs) + list(arguments_node.args)
    for each_argument in all_positional_arguments + list(arguments_node.kwonlyargs):
        if each_argument.arg == variable_name:
            return True
    if arguments_node.vararg is not None and arguments_node.vararg.arg == variable_name:
        return True
    if arguments_node.kwarg is not None and arguments_node.kwarg.arg == variable_name:
        return True
    return False


def _node_binds_name(node: ast.AST, variable_name: str) -> bool:
    """Return True when a single AST node binds variable_name in its enclosing scope."""
    if isinstance(node, ast.Assign):
        return any(_target_binds_name(each_target, variable_name) for each_target in node.targets)
    if isinstance(node, ast.AnnAssign):
        return _target_binds_name(node.target, variable_name)
    if isinstance(node, ast.AugAssign):
        return _target_binds_name(node.target, variable_name)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return _target_binds_name(node.target, variable_name)
    if isinstance(node, (ast.With, ast.AsyncWith)):
        for each_item in node.items:
            optional_target = each_item.optional_vars
            if optional_target is not None and _target_binds_name(optional_target, variable_name):
                return True
        return False
    if isinstance(node, ast.ExceptHandler):
        return node.name == variable_name
    if isinstance(node, ast.NamedExpr):
        return _target_binds_name(node.target, variable_name)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        for each_alias in node.names:
            bound_name = each_alias.asname if each_alias.asname is not None else each_alias.name.split(".")[0]
            if bound_name == variable_name:
                return True
        return False
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == variable_name
    return False


def _body_binds_name_recursively(all_body_statements: list[ast.stmt], variable_name: str) -> bool:
    """Return True when any node reachable within all_body_statements binds variable_name.

    Walks the body using a stack, descending into control-flow constructs
    (if/for/while/try/with) but treating nested function, async-function,
    class, and lambda definitions as opaque: their bodies belong to a
    different scope and do not affect bindings in the enclosing one.
    Function/class definitions themselves still bind their own name in
    the enclosing scope, which is handled by _node_binds_name.
    """
    nodes_to_visit: list[ast.AST] = list(all_body_statements)
    while nodes_to_visit:
        current_node = nodes_to_visit.pop()
        if _node_binds_name(current_node, variable_name):
            return True
        if isinstance(current_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        nodes_to_visit.extend(ast.iter_child_nodes(current_node))
    return False


def _scope_shadows_name(
    scope_node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    variable_name: str,
) -> bool:
    """Return True when scope_node locally binds variable_name.

    Detects every binding form Python treats as a local assignment:
    plain ``Assign``, annotated ``AnnAssign``, augmented ``AugAssign``,
    ``for`` targets, ``with`` as-targets, ``except`` handler names,
    walrus ``NamedExpr`` targets, ``import`` and ``from`` bindings
    (base name or ``as`` alias), nested function/class definitions
    (whose own name binds locally), and function parameters for
    ``FunctionDef`` / ``AsyncFunctionDef`` scopes. Bindings are
    detected at any nesting depth inside control-flow constructs;
    nested function, async-function, class, and lambda bodies are
    treated as opaque because their contents live in a different scope.
    """
    if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if _function_arguments_bind_name(scope_node.args, variable_name):
            return True
    return _body_binds_name_recursively(list(scope_node.body), variable_name)


def _walk_scope_skipping_shadowed(
    scope_node: ast.AST,
    variable_name: str,
) -> list[ast.AST]:
    """Walk all nodes in a scope, skipping nested function/class bodies that shadow variable_name."""
    collected: list[ast.AST] = []
    nodes_to_visit: list[ast.AST] = [scope_node]
    while nodes_to_visit:
        current = nodes_to_visit.pop()
        collected.append(current)
        for each_child in ast.iter_child_nodes(current):
            if (
                isinstance(each_child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and each_child is not scope_node
                and _scope_shadows_name(each_child, variable_name)
            ):
                continue
            nodes_to_visit.append(each_child)
    return collected


def _collect_mock_field_accesses_in_scope(
    scope_node: ast.AST,
    mock_name: str,
) -> list[tuple[str, int]]:
    """Return (field_name, line_number) for attribute or subscript accesses on mock_name within a scope.

    Skips nested function/class bodies that locally redefine the same mock
    variable to avoid false positives from name shadowing.
    """
    accesses: list[tuple[str, int]] = []
    for each_node in _walk_scope_skipping_shadowed(scope_node, mock_name):
        if isinstance(each_node, ast.Attribute):
            if isinstance(each_node.value, ast.Name) and each_node.value.id == mock_name:
                if isinstance(each_node.ctx, ast.Load):
                    if each_node.attr in ALL_BUILTIN_DICT_METHOD_NAMES:
                        continue
                    accesses.append((each_node.attr, each_node.lineno))
        elif isinstance(each_node, ast.Subscript):
            if isinstance(each_node.value, ast.Name) and each_node.value.id == mock_name:
                if isinstance(each_node.ctx, ast.Load):
                    slice_node = each_node.slice
                    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                        accesses.append((slice_node.value, each_node.lineno))
    return accesses


def _collect_mock_attribute_assignments_in_scope(
    scope_node: ast.AST,
    mock_name: str,
) -> set[str]:
    """Return field names assigned on a mock variable within a scope.

    Collects both attribute assignments (mock_x.field = ...) and subscript
    assignments with constant string keys (mock_x['field'] = ...).

    Skips nested function/class bodies that locally redefine the same mock
    variable, mirroring _collect_mock_field_accesses_in_scope so an outer
    mock's known-fields set cannot absorb assignments made on a shadowed
    inner mock of the same name.
    """
    assigned_fields: set[str] = set()
    for each_node in _walk_scope_skipping_shadowed(scope_node, mock_name):
        if not isinstance(each_node, ast.Assign):
            continue
        for each_target in each_node.targets:
            if (
                isinstance(each_target, ast.Attribute)
                and isinstance(each_target.value, ast.Name)
                and each_target.value.id == mock_name
            ):
                assigned_fields.add(each_target.attr)
            elif (
                isinstance(each_target, ast.Subscript)
                and isinstance(each_target.value, ast.Name)
                and each_target.value.id == mock_name
                and isinstance(each_target.slice, ast.Constant)
                and isinstance(each_target.slice.value, str)
            ):
                assigned_fields.add(each_target.slice.value)
    return assigned_fields


def _collect_scoped_mock_definitions(
    module_tree: ast.Module,
) -> list[tuple[int, str, set[str], int, ast.AST]]:
    """Return (scope_id, mock_name, declared_keys, definition_line, scope_node) for each mock.

    Keyed by (scope_node id, variable_name) so the same mock name in two different
    test functions is tracked independently. Scope is the enclosing function node,
    or the module node for module-level assignments.
    """
    scope_definitions: list[tuple[int, str, set[str], int, ast.AST]] = []
    for each_scope in ast.walk(module_tree):
        if not isinstance(each_scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            continue
        scope_body = each_scope.body
        for each_stmt in scope_body:
            if not isinstance(each_stmt, ast.Assign):
                continue
            for each_target in each_stmt.targets:
                if not isinstance(each_target, ast.Name):
                    continue
                target_name = each_target.id
                if not (target_name.startswith("mock_") or target_name.startswith("MOCK_")):
                    continue
                mock_keys = _collect_mock_dict_keys(each_stmt.value)
                if mock_keys is not None:
                    scope_definitions.append(
                        (id(each_scope), target_name, mock_keys, each_stmt.lineno, each_scope)
                    )
                elif isinstance(each_stmt.value, ast.Call):
                    scope_definitions.append(
                        (id(each_scope), target_name, set(), each_stmt.lineno, each_scope)
                    )
    return scope_definitions


def check_incomplete_mocks(content: str, file_path: str) -> None:
    """Emit stderr advisories when a mock dict/object is missing fields that are accessed.

    Scans test files for variables named mock_* or MOCK_* whose value is a dict
    literal. Each mock definition is keyed by (scope_node_id, variable_name) so
    the same name in different test functions is checked independently. Advisories
    are deduplicated per (mock_name, field_name) pair within each scope.

    This is advisory-only (no return value, no blocking).
    """
    if not is_test_file(file_path):
        return

    try:
        module_tree = ast.parse(content)
    except SyntaxError:
        return

    all_scoped_definitions = _collect_scoped_mock_definitions(module_tree)

    for each_scope_id, each_mock_name, each_declared_keys, each_definition_line, each_scope_node in all_scoped_definitions:
        assigned_attributes = _collect_mock_attribute_assignments_in_scope(each_scope_node, each_mock_name)
        all_known_fields = each_declared_keys | assigned_attributes
        field_accesses = _collect_mock_field_accesses_in_scope(each_scope_node, each_mock_name)
        already_advised: set[tuple[str, str]] = set()
        for each_accessed_field, each_access_line in field_accesses:
            if each_accessed_field in all_known_fields:
                continue
            advisory_key = (each_mock_name, each_accessed_field)
            if advisory_key in already_advised:
                continue
            already_advised.add(advisory_key)
            print(
                f"[CODE_RULES advisory] Line {each_definition_line}: mock {each_mock_name}"
                f" missing field {each_accessed_field} accessed at line {each_access_line}",
                file=sys.stderr,
            )
