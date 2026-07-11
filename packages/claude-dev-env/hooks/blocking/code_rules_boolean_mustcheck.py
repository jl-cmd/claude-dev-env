"""Boolean naming-prefix and ignored must-check-return checks."""

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
    _scope_violations_to_changed_lines,
    is_hook_infrastructure,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    MAX_IGNORED_MUST_CHECK_RETURN_ISSUES,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_BOOLEAN_NAME_PREFIXES,
    ALL_MUST_CHECK_RETURN_FUNCTION_NAMES,
    ALL_SELF_AND_CLS_PARAMETER_NAMES,
    UPPER_SNAKE_CONSTANT_PATTERN,
)


def _is_bool_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _rhs_names_if_all_bool(value_node: ast.AST, target_node: ast.AST) -> list[str]:
    """Return names from a tuple assignment target when every RHS element is a bool constant.

    Handles cases like `valid, permitted = True, False` where target is a Tuple
    and value is a Tuple of bool constants. Returns empty list otherwise.
    """
    if not isinstance(target_node, ast.Tuple):
        return []
    if not isinstance(value_node, ast.Tuple):
        return []
    if len(target_node.elts) != len(value_node.elts):
        return []
    if not all(_is_bool_constant(element) for element in value_node.elts):
        return []
    names: list[str] = []
    for each_element in target_node.elts:
        if isinstance(each_element, ast.Name):
            names.append(each_element.id)
    return names


def _assign_target_names_for_bool(node: ast.Assign) -> list[str]:
    if not node.targets:
        return []
    names: list[str] = []
    for each_target in node.targets:
        if isinstance(each_target, ast.Name) and _is_bool_constant(node.value):
            names.append(each_target.id)
        else:
            names.extend(_rhs_names_if_all_bool(node.value, each_target))
    return names


def _annassign_target_name_for_bool(node: ast.AnnAssign) -> list[str]:
    if not isinstance(node.target, ast.Name):
        return []
    is_annotation_bool_type = isinstance(node.annotation, ast.Name) and node.annotation.id == "bool"
    is_value_bool_constant = node.value is not None and _is_bool_constant(node.value)
    if is_annotation_bool_type and is_value_bool_constant:
        return [node.target.id]
    return []


def _walrus_name_for_bool(node: ast.NamedExpr) -> list[str]:
    if not isinstance(node.target, ast.Name):
        return []
    if not _is_bool_constant(node.value):
        return []
    return [node.target.id]


def _collect_boolean_assignments(tree: ast.Module) -> list[tuple[str, int, bool]]:
    """Collect boolean-constant assignments with (name, line_number, is_upper_snake_scope).

    `is_upper_snake_scope` is True for module-level statements and direct class body
    statements, where UPPER_SNAKE constants are acceptable (dataclass fields, class
    constants). Function/method scope is False.

    Invariant: relies on `ast.walk` returning the same node instances that were
    stored in `upper_snake_scope_ids` via their `id()`. Do not call this helper
    on a tree that has been rebuilt through an `ast.NodeTransformer` — the
    transformer may replace nodes with fresh instances, and the identity-based
    scope tagging will silently fail for the replaced nodes.
    """
    upper_snake_scope_ids: set[int] = set()
    for each_statement in tree.body:
        upper_snake_scope_ids.add(id(each_statement))
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.ClassDef):
            for each_class_statement in each_node.body:
                upper_snake_scope_ids.add(id(each_class_statement))
    collected: list[tuple[str, int, bool]] = []
    for each_node in ast.walk(tree):
        names: list[str] = []
        line_number = 0
        if isinstance(each_node, ast.Assign):
            names = _assign_target_names_for_bool(each_node)
            line_number = each_node.lineno
        elif isinstance(each_node, ast.AnnAssign):
            names = _annassign_target_name_for_bool(each_node)
            line_number = each_node.lineno
        elif isinstance(each_node, ast.NamedExpr):
            names = _walrus_name_for_bool(each_node)
            line_number = each_node.lineno
        if not names:
            continue
        is_in_upper_snake_scope = id(each_node) in upper_snake_scope_ids
        for each_name in names:
            collected.append((each_name, line_number, is_in_upper_snake_scope))
    return collected


def _argument_is_boolean(argument_node: ast.arg, default_node: ast.expr | None) -> bool:
    annotation_is_bool = (
        isinstance(argument_node.annotation, ast.Name)
        and argument_node.annotation.id == "bool"
    )
    default_is_bool = default_node is not None and _is_bool_constant(default_node)
    return annotation_is_bool or default_is_bool


def _bool_parameters_for_function(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[str, int]]:
    arguments = function_node.args
    positional_arguments = arguments.posonlyargs + arguments.args
    positional_defaults = arguments.defaults
    leading_without_default = len(positional_arguments) - len(positional_defaults)
    bool_parameters: list[tuple[str, int]] = []
    for each_position, each_argument in enumerate(positional_arguments):
        default_index = each_position - leading_without_default
        default_node = (
            positional_defaults[default_index] if default_index >= 0 else None
        )
        if each_argument.arg in ALL_SELF_AND_CLS_PARAMETER_NAMES:
            continue
        if _argument_is_boolean(each_argument, default_node):
            bool_parameters.append((each_argument.arg, each_argument.lineno))
    for each_argument, each_default in zip(arguments.kwonlyargs, arguments.kw_defaults):
        if each_argument.arg in ALL_SELF_AND_CLS_PARAMETER_NAMES:
            continue
        if _argument_is_boolean(each_argument, each_default):
            bool_parameters.append((each_argument.arg, each_argument.lineno))
    return bool_parameters


def _collect_bool_parameter_names(tree: ast.Module) -> list[tuple[str, int]]:
    """Collect (name, line_number) for boolean-typed function parameters.

    A parameter counts as boolean when its annotation is the ``bool`` name or
    its default is a boolean literal. ``self`` and ``cls`` are skipped.

    Args:
        tree: The parsed module to inspect.

    Returns:
        Each boolean parameter as a (name, line_number) pair.
    """
    bool_parameters: list[tuple[str, int]] = []
    for each_node in ast.walk(tree):
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bool_parameters.extend(_bool_parameters_for_function(each_node))
    return bool_parameters


def check_boolean_naming(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag boolean assignments and parameters whose name lacks a required prefix.

    The caller passes the reconstructed full file as *content* so ``ast.parse``
    sees a complete module rather than an Edit's ``new_string`` fragment, which is
    rarely valid standalone Python. Findings are then scoped to *all_changed_lines*
    so an Edit blocks on the unprefixed boolean it just introduced while a
    pre-existing violation on an untouched line does not block the edit.

    Args:
        content: The source text to inspect — the reconstructed full file on an
            Edit so the parse succeeds.
        file_path: The path the source will be written to, used for exemptions.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when its source line intersects the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line.

    Returns:
        One issue per unprefixed boolean assignment and parameter, scoped to the
        changed lines unless *defer_scope_to_caller* is True or *all_changed_lines*
        is None. This check has no module cap.
    """
    if is_test_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError as parse_error:
        print(
            f"[CODE_RULES advisory] {file_path}: boolean-naming check skipped - "
            f"SyntaxError at line {parse_error.lineno}: {parse_error.msg}",
            file=sys.stderr,
        )
        return []
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_name, each_line_number, each_is_in_upper_snake_scope in _collect_boolean_assignments(tree):
        if len(each_name) == 1:
            continue
        if each_is_in_upper_snake_scope and UPPER_SNAKE_CONSTANT_PATTERN.match(each_name):
            continue
        if each_name.startswith(ALL_BOOLEAN_NAME_PREFIXES):
            continue
        boolean_prefix_suffix = "is_/has_/should_/can_/was_/did_"
        message = (
            f"Line {each_line_number}: Boolean {each_name} - prefix with "
            f"{boolean_prefix_suffix}"
        )
        all_violations_in_walk_order.append(
            (range(each_line_number, each_line_number + 1), message)
        )
    for each_name, each_line_number in _collect_bool_parameter_names(tree):
        if len(each_name) == 1:
            continue
        if each_name.startswith(ALL_BOOLEAN_NAME_PREFIXES):
            continue
        boolean_prefix_suffix = "is_/has_/should_/can_/was_/did_"
        message = (
            f"Line {each_line_number}: Boolean parameter {each_name} - prefix with "
            f"{boolean_prefix_suffix}"
        )
        all_violations_in_walk_order.append(
            (range(each_line_number, each_line_number + 1), message)
        )
    return _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )


def _called_terminal_name(call_node: ast.Call) -> str | None:
    callee = call_node.func
    if isinstance(callee, ast.Name):
        return callee.id
    if isinstance(callee, ast.Attribute):
        return callee.attr
    return None


def check_ignored_must_check_return(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag bare-expression calls whose discarded return is the only failure signal.

    Functions in ``ALL_MUST_CHECK_RETURN_FUNCTION_NAMES`` report success or failure
    solely through their return value. A bare-statement call discards that value,
    so the caller silently proceeds on failure. Bare ``ast.Expr`` calls are flagged,
    including a bare ``await``-wrapped call (``await find_and_click(...)`` as a
    statement); an assigned or branched-on call is exempt.

    The caller passes the reconstructed full file as *content* so ``ast.parse``
    sees a complete module rather than an Edit's ``new_string`` fragment, which is
    rarely valid standalone Python (a bare ``await find_and_click(...)`` line is a
    SyntaxError on its own). Findings are then scoped to *all_changed_lines* so an
    Edit blocks on the discarded return it just introduced while a pre-existing
    violation on an untouched line does not block the edit.

    Args:
        content: The source text to inspect — the reconstructed full file on an
            Edit so the parse succeeds.
        file_path: The path the source will be written to, used for exemptions.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when the bare call's line intersects the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line.

    Returns:
        One issue per discarded must-check return, scoped to the changed lines
        unless *defer_scope_to_caller* is True or *all_changed_lines* is None. When
        *defer_scope_to_caller* is True every violation is returned uncapped so the
        gate can scope by added line and apply its own ceiling; otherwise the
        terminal result is capped at the module limit.
    """
    if is_test_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Expr):
            continue
        expression_value = each_node.value
        call_node = (
            expression_value.value
            if isinstance(expression_value, ast.Await)
            else expression_value
        )
        if not isinstance(call_node, ast.Call):
            continue
        called_name = _called_terminal_name(call_node)
        if called_name is None or called_name not in ALL_MUST_CHECK_RETURN_FUNCTION_NAMES:
            continue
        end_line_number = each_node.end_lineno or each_node.lineno
        line_span = range(each_node.lineno, end_line_number + 1)
        message = (
            f"Line {each_node.lineno}: return value of {called_name}() is discarded - "
            "assign and check it (the boolean/outcome is the only failure signal)"
        )
        all_violations_in_walk_order.append((line_span, message))
    scoped_issues = _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
    if defer_scope_to_caller:
        return scoped_issues
    return scoped_issues[:MAX_IGNORED_MUST_CHECK_RETURN_ISSUES]
