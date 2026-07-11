"""Test-module dead-scaffolding checks: dead constant, unused helper parameter.

Two checks run only on a genuine test module (``test_*.py``, ``*_test.py``,
``*.spec.*``, ``conftest.py``, or a file under a ``tests/`` directory), where
scaffolding left after an edit hides in plain sight. A test file exports
nothing, so a single-file scan proves a symbol dead: when a removed
monkeypatch line was the last reader of a module constant, or the last user
of a private helper's parameter, the leftover is dead code the checks flag at
Write/Edit time.
"""

import ast
from typing import TypeGuard

from code_rules_shared import is_strict_test_file
from hooks_constants.test_layout_constants import (
    CLASS_METHOD_FIRST_PARAMETER_NAME,
    DEAD_TEST_CONSTANT_GUIDANCE,
    FIXTURE_DECORATOR_MARKER,
    MAX_TEST_LAYOUT_ISSUES,
    MINIMUM_CONSTANT_NAME_LENGTH,
    PRIVATE_NAME_PREFIX,
    SELF_PARAMETER_NAME,
    UNUSED_TEST_HELPER_PARAMETER_GUIDANCE,
)

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _parse_module(content: str) -> ast.Module | None:
    """Return the parsed module, or None when the content does not parse."""
    try:
        return ast.parse(content)
    except SyntaxError:
        return None


def _is_constant_name(name: str) -> bool:
    """Return whether a name is an UPPER_SNAKE constant identifier.

    A leading underscore is allowed, so a private module constant such as
    ``_ABSENT_DOTENV_FILENAME`` qualifies.
    """
    if len(name) < MINIMUM_CONSTANT_NAME_LENGTH:
        return False
    if not name.replace("_", "").isalnum():
        return False
    return name == name.upper() and any(each_char.isalpha() for each_char in name)


def _assignment_targets(statement: ast.stmt) -> list[ast.expr]:
    """Return the assignment targets of a plain or annotated assignment."""
    if isinstance(statement, ast.Assign):
        return list(statement.targets)
    if isinstance(statement, ast.AnnAssign) and statement.value is not None:
        return [statement.target]
    return []


def _statement_constant_targets(statement: ast.stmt) -> list[tuple[str, int]]:
    """Return (name, line) for each UPPER_SNAKE constant one statement binds."""
    named_targets: list[tuple[str, int]] = []
    for each_target in _assignment_targets(statement):
        if isinstance(each_target, ast.Name) and _is_constant_name(each_target.id):
            named_targets.append((each_target.id, statement.lineno))
    return named_targets


def _module_constant_targets(tree: ast.Module) -> list[tuple[str, int]]:
    """Return (name, line) for every module-scope UPPER_SNAKE constant, in order."""
    constant_targets: list[tuple[str, int]] = []
    for each_statement in tree.body:
        constant_targets.extend(_statement_constant_targets(each_statement))
    return constant_targets


def _referenced_names(tree: ast.Module) -> set[str]:
    """Return every name the module reads plus every string literal it holds.

    A ``Load``-context name is a read; a ``Store`` target (the constant's own
    definition) is not, so a constant read nowhere else stays out of the set.
    String literals are unioned in so an ``__all__`` or ``getattr`` string name
    still counts.
    """
    all_nodes = list(ast.walk(tree))
    load_names = {
        each_node.id
        for each_node in all_nodes
        if isinstance(each_node, ast.Name) and isinstance(each_node.ctx, ast.Load)
    }
    literal_values = {
        each_node.value
        for each_node in all_nodes
        if isinstance(each_node, ast.Constant) and isinstance(each_node.value, str)
    }
    return load_names | literal_values


def _dead_constant_messages(tree: ast.Module, referenced_names: set[str]) -> list[str]:
    """Return one message per module constant absent from the referenced set."""
    issues: list[str] = []
    for each_name, each_line in _module_constant_targets(tree):
        if each_name in referenced_names:
            continue
        issues.append(
            f"Line {each_line}: constant {each_name!r} - {DEAD_TEST_CONSTANT_GUIDANCE}"
        )
        if len(issues) >= MAX_TEST_LAYOUT_ISSUES:
            break
    return issues


def check_dead_test_module_constant(content: str, file_path: str) -> list[str]:
    """Flag a module-level constant in a test file that no other line reads.

    ::

        a private UPPER_SNAKE constant that no Load reference and no string
        literal in the module names   ->   dead scaffolding, flag it

    A test module exports nothing, so a constant read by no reference and named
    in no string literal is dead code left after an edit.

    Args:
        content: The post-edit file content under validation.
        file_path: The destination path, used for the test-file gate.

    Returns:
        One message per dead constant, capped at the configured maximum.
    """
    if not is_strict_test_file(file_path):
        return []
    tree = _parse_module(content)
    if tree is None:
        return []
    return _dead_constant_messages(tree, _referenced_names(tree))


def _node_names_fixture(node: ast.AST) -> bool:
    """Return whether one decorator sub-node spells the pytest fixture marker."""
    if isinstance(node, ast.Name):
        return FIXTURE_DECORATOR_MARKER in node.id
    if isinstance(node, ast.Attribute):
        return FIXTURE_DECORATOR_MARKER in node.attr
    return False


def _has_fixture_decorator(function_node: _FunctionNode) -> bool:
    """Return whether a function carries a pytest fixture decorator.

    A fixture parameter is injected by pytest and read by name only, so a
    fixture must never be judged for unused parameters.
    """
    for each_decorator in function_node.decorator_list:
        if any(
            _node_names_fixture(each_node) for each_node in ast.walk(each_decorator)
        ):
            return True
    return False


def _is_judged_parameter(parameter_name: str) -> bool:
    """Return whether a parameter name is worth judging for being unread.

    ``self`` and ``cls`` are receiver names, and an underscore-prefixed name is
    a conventional throwaway, so none of the three are judged.
    """
    if parameter_name in {SELF_PARAMETER_NAME, CLASS_METHOD_FIRST_PARAMETER_NAME}:
        return False
    return not parameter_name.startswith(PRIVATE_NAME_PREFIX)


def _candidate_parameters(function_node: _FunctionNode) -> list[ast.arg]:
    """Return the parameters of a function worth judging for being unread."""
    arguments = function_node.args
    all_parameters = arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    return [each for each in all_parameters if _is_judged_parameter(each.arg)]


def _read_parameter_names(function_node: _FunctionNode) -> set[str]:
    """Return every name read anywhere in a function body."""
    return {
        each_node.id
        for each_node in ast.walk(function_node)
        if isinstance(each_node, ast.Name) and isinstance(each_node.ctx, ast.Load)
    }


def _unused_parameter_messages(function_node: _FunctionNode) -> list[str]:
    """Return one message per candidate parameter the function body never reads."""
    read_names = _read_parameter_names(function_node)
    issues: list[str] = []
    for each_parameter in _candidate_parameters(function_node):
        if each_parameter.arg in read_names:
            continue
        issues.append(
            f"Line {each_parameter.lineno}: parameter {each_parameter.arg!r}"
            f" on {function_node.name!r} - {UNUSED_TEST_HELPER_PARAMETER_GUIDANCE}"
        )
    return issues


def _is_private_plain_function(statement: ast.stmt) -> TypeGuard[_FunctionNode]:
    """Return whether a statement is a private, non-fixture module-level function."""
    if not isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
        return False
    if not statement.name.startswith(PRIVATE_NAME_PREFIX):
        return False
    return not _has_fixture_decorator(statement)


def check_unused_test_helper_parameter(content: str, file_path: str) -> list[str]:
    """Flag a parameter of a private test helper that its body never reads.

    ::

        def _configuration(monkeypatch, tmp_path):   neither read -> flag
            return DatabaseConfig.from_environment()

    A private module-level function carries no pytest fixture decorator, so its
    parameter is never injected by name, and one the body never reads is dead.

    Args:
        content: The post-edit file content under validation.
        file_path: The destination path, used for the test-file gate.

    Returns:
        One message per unused private-helper parameter, capped at the maximum.
    """
    if not is_strict_test_file(file_path):
        return []
    tree = _parse_module(content)
    if tree is None:
        return []
    issues: list[str] = []
    for each_statement in tree.body:
        if _is_private_plain_function(each_statement):
            issues.extend(_unused_parameter_messages(each_statement))
    return issues[:MAX_TEST_LAYOUT_ISSUES]
