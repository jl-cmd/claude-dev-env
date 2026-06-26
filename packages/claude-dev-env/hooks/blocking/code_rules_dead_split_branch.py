"""Dead-conditional-branch check for a truthiness test on an always-non-empty split."""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_path_utils import (  # noqa: E402
    is_config_file,
)
from code_rules_shared import (  # noqa: E402
    _collect_annotated_arguments,
    _walk_skipping_nested_function_defs,
    is_test_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_ALWAYS_NONEMPTY_SPLIT_METHOD_NAMES,
    DEAD_SPLIT_BRANCH_MESSAGE_SUFFIX,
    MAX_DEAD_SPLIT_BRANCH_ISSUES,
)


def _is_separator_split_call(call_node: ast.Call) -> bool:
    """Return True for an ``x.split(sep)`` / ``x.rsplit(sep)`` with a non-empty separator.

    ``str.split`` and ``bytes.split`` return a list holding at least one element
    whenever a separator argument is supplied, so the result is always truthy.
    Requiring a non-empty string or bytes literal separator keeps the guarantee
    airtight: ``split()`` with no argument can return an empty list, and an
    empty separator raises at runtime. The receiver is restricted to a bare
    ``Name`` or a string/bytes literal so an intermediate attribute chain such
    as a pandas ``s.str.split(",")`` — whose result is a Series, not a list —
    is not treated as an always-non-empty split.

    Args:
        call_node: The call expression on the right-hand side of an assignment.

    Returns:
        True when the call is a separator-bearing split that never returns an
        empty list.
    """
    function_node = call_node.func
    if not isinstance(function_node, ast.Attribute):
        return False
    if function_node.attr not in ALL_ALWAYS_NONEMPTY_SPLIT_METHOD_NAMES:
        return False
    receiver_node = function_node.value
    if isinstance(receiver_node, ast.Constant):
        if not isinstance(receiver_node.value, (str, bytes)):
            return False
    elif not isinstance(receiver_node, ast.Name):
        return False
    if not call_node.args:
        return False
    first_argument = call_node.args[0]
    if not isinstance(first_argument, ast.Constant):
        return False
    separator_value = first_argument.value
    if not isinstance(separator_value, (str, bytes)):
        return False
    return len(separator_value) > 0


def _separator_split_target_names(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    """Return names bound exactly once in the function from a separator split.

    A name qualifies when its single binding in the function body is an
    assignment whose value is a separator-bearing ``split`` / ``rsplit`` call,
    so the bound list is always truthy. A name bound more than once, or also a
    parameter, is excluded because a later rebinding could make it falsy.

    Args:
        function_node: The function whose body is inspected.

    Returns:
        The set of always-truthy split-result names safe to reason about.
    """
    all_store_counts: dict[str, int] = {}
    all_split_names: set[str] = set()
    for each_statement in function_node.body:
        for each_node in _walk_skipping_nested_function_defs(each_statement):
            if isinstance(each_node, ast.Name) and isinstance(each_node.ctx, ast.Store):
                all_store_counts[each_node.id] = (
                    all_store_counts.get(each_node.id, 0) + 1
                )
            if not isinstance(each_node, ast.Assign):
                continue
            if len(each_node.targets) != 1:
                continue
            assignment_target = each_node.targets[0]
            if not isinstance(assignment_target, ast.Name):
                continue
            if isinstance(each_node.value, ast.Call) and _is_separator_split_call(
                each_node.value
            ):
                all_split_names.add(assignment_target.id)
    all_parameter_names = {
        each_argument.arg
        for each_argument in _collect_annotated_arguments(function_node)
    }
    return {
        each_name
        for each_name in all_split_names
        if all_store_counts.get(each_name, 0) == 1
        and each_name not in all_parameter_names
    }


def _truthiness_target(
    test_node: ast.expr, all_candidate_names: set[str]
) -> str | None:
    """Return the candidate name a bare ``Name`` truthiness test reads, else None."""
    if isinstance(test_node, ast.Name) and test_node.id in all_candidate_names:
        return test_node.id
    return None


def _negated_truthiness_target(
    test_node: ast.expr, all_candidate_names: set[str]
) -> str | None:
    """Return the candidate name a ``not Name`` test reads, else None."""
    if not isinstance(test_node, ast.UnaryOp) or not isinstance(test_node.op, ast.Not):
        return None
    operand = test_node.operand
    if isinstance(operand, ast.Name) and operand.id in all_candidate_names:
        return operand.id
    return None


def _branch_finding_for_node(
    node: ast.AST, all_candidate_names: set[str]
) -> tuple[int, str] | None:
    """Return ``(line, name)`` when a node carries a dead branch, else None.

    A conditional expression always carries an else arm, so any truthiness test
    on a candidate name is a dead branch. An ``if`` statement only carries a
    dead else when it has one, while an ``if not name`` statement always has a
    dead body.
    """
    if isinstance(node, ast.IfExp):
        truthy_name = _truthiness_target(node.test, all_candidate_names)
        if truthy_name is not None:
            return node.lineno, truthy_name
        return _negated_branch_finding(node.test, node.lineno, all_candidate_names)
    if isinstance(node, ast.If):
        truthy_name = _truthiness_target(node.test, all_candidate_names)
        if truthy_name is not None and node.orelse:
            return node.lineno, truthy_name
        return _negated_branch_finding(node.test, node.lineno, all_candidate_names)
    return None


def _negated_branch_finding(
    test_node: ast.expr, line_number: int, all_candidate_names: set[str]
) -> tuple[int, str] | None:
    negated_name = _negated_truthiness_target(test_node, all_candidate_names)
    if negated_name is not None:
        return line_number, negated_name
    return None


def _dead_branch_findings(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_candidate_names: set[str],
) -> list[tuple[int, str]]:
    """Return every ``(line, name)`` dead-branch finding in the function body."""
    all_findings: list[tuple[int, str]] = []
    for each_statement in function_node.body:
        for each_node in _walk_skipping_nested_function_defs(each_statement):
            finding = _branch_finding_for_node(each_node, all_candidate_names)
            if finding is not None:
                all_findings.append(finding)
    return all_findings


def check_dead_split_truthiness_branch(content: str, file_path: str) -> list[str]:
    """Flag a conditional whose branch is unreachable after a separator split.

    ``str.split(sep)`` and ``bytes.split(sep)`` with a separator always return a
    list holding at least one element, so a value bound from such a call is
    always truthy. A conditional that tests that value's truthiness carries a
    dead branch: ``parts[0] if parts else fallback`` never reaches ``fallback``,
    and ``if not parts:`` never runs its body. Both the conditional-expression
    form and the ``if`` / ``if not`` statement form are reported, scoped to a
    value bound exactly once in the function from a separator split. Config
    files and test files are exempt.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per dead conditional branch found, capped at the module limit.
    """
    if is_test_file(file_path) or is_config_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_function_node in ast.walk(tree):
        if not isinstance(each_function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        all_candidate_names = _separator_split_target_names(each_function_node)
        if not all_candidate_names:
            continue
        for each_line, each_name in _dead_branch_findings(
            each_function_node, all_candidate_names
        ):
            issues.append(
                f"Line {each_line}: {each_name!r} {DEAD_SPLIT_BRANCH_MESSAGE_SUFFIX}"
            )
            if len(issues) >= MAX_DEAD_SPLIT_BRANCH_ISSUES:
                return issues
    return issues
