"""Blast-radius check: a raise inside per-item work must name what it stops."""

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
    is_hook_infrastructure,
    is_test_file,
)

from hooks_constants.blast_radius_constants import (  # noqa: E402
    ALL_BLAST_RADIUS_SUFFIXES,
    BLAST_RADIUS_MESSAGE_SUFFIX,
    MAX_BLAST_RADIUS_ISSUES,
)


def _raised_type_name(raise_node: ast.Raise) -> str | None:
    """Return the name of the exception type a raise statement constructs.

    Args:
        raise_node: The raise statement to read.

    Returns:
        The type name, or ``None`` for a bare re-raise or an unreadable form.
    """
    raised = raise_node.exc
    if raised is None:
        return None
    if isinstance(raised, ast.Call):
        raised = raised.func
    if isinstance(raised, ast.Name):
        return raised.id
    if isinstance(raised, ast.Attribute):
        return raised.attr
    return None


def _declares_blast_radius(type_name: str) -> bool:
    """Report whether an exception type name states what its failure stops.

    Args:
        type_name: The exception type name to inspect.

    Returns:
        ``True`` when the name ends in a recognized blast-radius suffix.
    """
    return any(type_name.endswith(each_suffix) for each_suffix in ALL_BLAST_RADIUS_SUFFIXES)


def _handler_names_blast_radius_type(handler: ast.ExceptHandler) -> bool:
    """Report whether an except clause catches a blast-radius-declaring type.

    Args:
        handler: The except clause to inspect.

    Returns:
        ``True`` when any caught type name carries a blast-radius suffix.
    """
    caught = handler.type
    if caught is None:
        return False
    all_caught = caught.elts if isinstance(caught, ast.Tuple) else [caught]
    for each_caught in all_caught:
        if isinstance(each_caught, ast.Name) and _declares_blast_radius(each_caught.id):
            return True
        if isinstance(each_caught, ast.Attribute) and _declares_blast_radius(each_caught.attr):
            return True
    return False


def _boundary_guarded_raise_lines(tree: ast.Module) -> set[int]:
    """Collect raise lines already sitting inside a blast-radius boundary.

    Args:
        tree: The parsed module to walk.

    Returns:
        The line numbers of raise statements enclosed by a try whose handlers
        name a blast-radius-declaring type.
    """
    all_guarded: set[int] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Try):
            continue
        if not any(_handler_names_blast_radius_type(each) for each in each_node.handlers):
            continue
        for each_body_node in each_node.body:
            for each_inner in ast.walk(each_body_node):
                if isinstance(each_inner, ast.Raise):
                    all_guarded.add(each_inner.lineno)
    return all_guarded


def _per_item_raise_nodes(tree: ast.Module) -> list[ast.Raise]:
    """Collect raise statements that sit inside a loop body.

    A raise reached only through per-item iteration ends every remaining item
    unless something declares otherwise, so those are the ones worth naming.

    Args:
        tree: The parsed module to walk.

    Returns:
        Every raise statement found under a for or while loop body.
    """
    all_raises: list[ast.Raise] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.For, ast.AsyncFor, ast.While)):
            continue
        for each_body_node in each_node.body:
            for each_inner in ast.walk(each_body_node):
                if isinstance(each_inner, ast.Raise):
                    all_raises.append(each_inner)
    return all_raises


def check_blast_radius_declared(content: str, file_path: str) -> list[str]:
    """Flag raises inside per-item work that never say what they stop.

    A raise reached through a loop body ends the whole batch by default, so a
    one-item defect discards every item that already succeeded. Naming the type
    ``*RunFatal`` or ``*ItemBlocked`` states the intent, and a boundary catching
    a declared type already handles it.

    Args:
        content: The file body to inspect.
        file_path: The path the body will be written to.

    Returns:
        One advisory line per undeclared raise, capped at the configured maximum.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    all_guarded_lines = _boundary_guarded_raise_lines(parsed_tree)
    all_issues: list[str] = []
    all_reported_lines: set[int] = set()
    for each_raise in _per_item_raise_nodes(parsed_tree):
        if each_raise.lineno in all_guarded_lines or each_raise.lineno in all_reported_lines:
            continue
        type_name = _raised_type_name(each_raise)
        if type_name is None or _declares_blast_radius(type_name):
            continue
        all_reported_lines.add(each_raise.lineno)
        all_issues.append(f"Line {each_raise.lineno}: {type_name} {BLAST_RADIUS_MESSAGE_SUFFIX}")
        if len(all_issues) >= MAX_BLAST_RADIUS_ISSUES:
            break
    return all_issues
