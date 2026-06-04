"""Test-mode branching in production and bare-except checks."""

import ast
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_shared import (  # noqa: E402
    _walk_skipping_type_checking_blocks,
    is_hook_infrastructure,
    is_test_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES,
    ALL_TEST_INDICATING_ENVIRONMENT_VARIABLE_NAMES,
    MAX_BARE_EXCEPT_ISSUES,
    MAX_TEST_BRANCHING_ISSUES,
)


def _string_constant_value(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_environ_attribute(node: ast.expr) -> bool:
    if isinstance(node, ast.Attribute) and node.attr == "environ":
        return isinstance(node.value, ast.Name) and node.value.id == "os"
    return False


def _environ_get_call_argument_names(call_node: ast.Call) -> list[str]:
    function_node = call_node.func
    if not isinstance(function_node, ast.Attribute):
        return []
    if function_node.attr != "get":
        return []
    if not _is_environ_attribute(function_node.value):
        return []
    if not call_node.args:
        return []
    first_argument = _string_constant_value(call_node.args[0])
    return [first_argument] if first_argument is not None else []


def _environ_subscript_key_names(subscript_node: ast.Subscript) -> list[str]:
    if not _is_environ_attribute(subscript_node.value):
        return []
    key = _string_constant_value(subscript_node.slice)
    return [key] if key is not None else []


def _environ_membership_key_names(compare_node: ast.Compare) -> list[str]:
    if not compare_node.ops:
        return []
    if not isinstance(compare_node.ops[0], (ast.In, ast.NotIn)):
        return []
    if not compare_node.comparators:
        return []
    if not _is_environ_attribute(compare_node.comparators[0]):
        return []
    key = _string_constant_value(compare_node.left)
    return [key] if key is not None else []


def _collect_test_env_variable_references(parsed_tree: ast.AST) -> list[tuple[int, str]]:
    references: list[tuple[int, str]] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        candidate_names: list[str] = []
        if isinstance(each_node, ast.Call):
            candidate_names = _environ_get_call_argument_names(each_node)
        elif isinstance(each_node, ast.Subscript):
            candidate_names = _environ_subscript_key_names(each_node)
        elif isinstance(each_node, ast.Compare):
            candidate_names = _environ_membership_key_names(each_node)
        for each_candidate_name in candidate_names:
            if each_candidate_name in ALL_TEST_INDICATING_ENVIRONMENT_VARIABLE_NAMES:
                references.append((each_node.lineno, each_candidate_name))
    return references


def check_test_branching_in_production(content: str, file_path: str) -> list[str]:
    """Flag production code that branches on TESTING-style env vars.

    Production code reading TESTING / PYTEST_CURRENT_TEST creates two
    parallel implementations and hides bugs. Use dependency injection
    (override the dependency in tests) instead.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    references = _collect_test_env_variable_references(parsed_tree)
    references.sort(key=lambda each_reference: each_reference[0])

    issues: list[str] = []
    already_reported_lines: set[int] = set()
    for each_line_number, each_variable_name in references:
        if each_line_number in already_reported_lines:
            continue
        already_reported_lines.add(each_line_number)
        issues.append(
            f"Line {each_line_number}: Production code reads test indicator '{each_variable_name}' — "
            "use dependency injection so production stays single-path"
        )
        if len(issues) >= MAX_TEST_BRANCHING_ISSUES:
            break

    return issues


def _bare_except_handler_label(handler_node: ast.ExceptHandler) -> str | None:
    """Return a label for handlers we flag, or None for safe handlers."""
    handler_type = handler_node.type
    if handler_type is None:
        return "bare except:"
    if isinstance(handler_type, ast.Name) and handler_type.id in ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES:
        return f"except {handler_type.id}:"
    if (
        isinstance(handler_type, ast.Attribute)
        and handler_type.attr in ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES
    ):
        return f"except {handler_type.attr}:"
    if isinstance(handler_type, ast.Tuple):
        banned_names: list[str] = []
        for each_element in handler_type.elts:
            if isinstance(each_element, ast.Name) and each_element.id in ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES:
                banned_names.append(each_element.id)
            elif (
                isinstance(each_element, ast.Attribute)
                and each_element.attr in ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES
            ):
                banned_names.append(each_element.attr)
        if banned_names:
            return f"except {', '.join(banned_names)} (in tuple):"
    return None


def check_bare_except(content: str, file_path: str) -> list[str]:
    """Flag bare/over-broad exception handlers in production code.

    ``except:`` and ``except BaseException:`` swallow KeyboardInterrupt and
    SystemExit; ``except Exception:`` hides bugs by catching nearly every
    error class. Production code should name the specific exception(s) it
    intends to catch
    (a tuple form like `except (ValueError, KeyError):` is fine).
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, ast.ExceptHandler):
            continue
        handler_label = _bare_except_handler_label(each_node)
        if handler_label is None:
            continue
        issues.append(
            f"Line {each_node.lineno}: {handler_label} is over-broad — name the "
            "specific exception(s) you intend to handle"
        )
        if len(issues) >= MAX_BARE_EXCEPT_ISSUES:
            break
    return issues
