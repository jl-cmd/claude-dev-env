"""Recognizer for the repo's sys.path bootstrap-guard idiom.

Split out of python_style_checks.py to keep that file under its line cap.
Tells the import-order check whether a run of module-level statements is that
idiom rather than ordinary code: `check_sys_path_insert_deduplication_guard`
(code_rules_paths_syspath.py) requires every `sys.path.insert` call to sit
behind `if <path> not in sys.path:`, and the import-order check must not
penalize a file for following that guard.
"""

import ast


def _is_sys_path_insert_expression(expression: ast.expr) -> bool:
    """Return True for a `sys.path.insert(...)` call expression."""
    if not isinstance(expression, ast.Call):
        return False
    function_reference = expression.func
    if not isinstance(function_reference, ast.Attribute) or function_reference.attr != "insert":
        return False
    receiver = function_reference.value
    if not isinstance(receiver, ast.Attribute) or receiver.attr != "path":
        return False
    receiver_value = receiver.value
    return isinstance(receiver_value, ast.Name) and receiver_value.id == "sys"


def _is_sys_path_bootstrap_guard(statement: ast.stmt) -> bool:
    """Return True for `if <expr> not in sys.path: sys.path.insert(...)`.

    Only the then-branch is inspected, matching the scope
    `check_sys_path_insert_deduplication_guard` itself checks.
    """
    if not isinstance(statement, ast.If):
        return False
    membership_test = statement.test
    if not isinstance(membership_test, ast.Compare) or len(membership_test.ops) != 1:
        return False
    if not isinstance(membership_test.ops[0], ast.NotIn):
        return False
    membership_target = membership_test.comparators[0]
    if not isinstance(membership_target, ast.Attribute) or membership_target.attr != "path":
        return False
    if not isinstance(membership_target.value, ast.Name) or membership_target.value.id != "sys":
        return False
    return any(
        isinstance(each_body_statement, ast.Expr)
        and _is_sys_path_insert_expression(each_body_statement.value)
        for each_body_statement in statement.body
    )


def _is_plain_assignment_statement(statement: ast.stmt) -> bool:
    """Return True for a single-target module-level `name = value` assignment."""
    return (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
    )


def is_sys_path_bootstrap_prelude(all_pending_statements: list[ast.stmt]) -> bool:
    """Return True when *all_pending_statements* form the repo's sys.path bootstrap idiom.

    Writing the mandated dedup guard takes a preceding `<path> = ...`
    assignment and the guarded `if` itself — both ordinary, non-import
    statements that would otherwise read as ordinary code to an import-order
    check and flag every import that follows.

    A run of statements between two import blocks is accepted as this
    bootstrap prelude, rather than as ordinary code, when it contains at
    least one real guard and every other statement in the same run is a
    plain assignment — the shape a `path = ...` line or an unrelated
    same-block constant both take. A bare `sys.path.insert` with no guard,
    or any def/class/call statement, is not part of this shape and still
    counts as ordinary code.
    """
    if not any(_is_sys_path_bootstrap_guard(each) for each in all_pending_statements):
        return False
    return all(
        _is_sys_path_bootstrap_guard(each) or _is_plain_assignment_statement(each)
        for each in all_pending_statements
    )
