"""Hardcoded user-path and sys.path.insert deduplication-guard checks."""

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
    _build_parent_map,
    is_hook_infrastructure,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)
from code_rules_string_magic import (  # noqa: E402
    _collect_docstring_node_ids,
)

from hooks_constants.hardcoded_user_path_constants import (  # noqa: E402
    HARDCODED_USER_PATH_GUIDANCE,
    HARDCODED_USER_PATH_PATTERN,
    MAX_HARDCODED_USER_PATH_ISSUES,
)
from hooks_constants.sys_path_insert_constants import (  # noqa: E402
    MAX_SYS_PATH_INSERT_ISSUES,
    SYS_PATH_INSERT_GUIDANCE,
    SYS_PATH_INSERT_MINIMUM_ARGUMENT_COUNT,
)


def check_hardcoded_user_paths(content: str, file_path: str) -> list[str]:
    """Flag string literals naming a specific user's home directory.

    Catches non-portable paths like `C:/Users/jon/...`, `/Users/alice/...`,
    and `/home/bob/...` that surface in production code.
    Test files, config/ files, workflow registry files, migration files,
    and hook infrastructure files are exempt. Hook infrastructure exemption
    matches the pattern used by check_library_print and other check
    functions, and prevents the enforcer from self-blocking on its own
    HARDCODED_USER_PATH_PATTERN definition.
    """
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    docstring_node_ids = _collect_docstring_node_ids(tree)
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Constant):
            continue
        if not isinstance(each_node.value, str):
            continue
        if id(each_node) in docstring_node_ids:
            continue
        match = HARDCODED_USER_PATH_PATTERN.search(each_node.value)
        if match is None:
            continue
        issues.append(
            f"Line {each_node.lineno}: hardcoded user path {match.group(0)!r}"
            f" — {HARDCODED_USER_PATH_GUIDANCE}"
        )
        if len(issues) >= MAX_HARDCODED_USER_PATH_ISSUES:
            break
    return issues


def _is_sys_path_insert_call(call_node: ast.Call) -> bool:
    function_reference = call_node.func
    if not isinstance(function_reference, ast.Attribute) or function_reference.attr != "insert":
        return False
    receiver = function_reference.value
    if not isinstance(receiver, ast.Attribute) or receiver.attr != "path":
        return False
    receiver_value = receiver.value
    return isinstance(receiver_value, ast.Name) and receiver_value.id == "sys"


def _is_sys_path_membership_if_test(if_test_expression: ast.AST) -> bool:
    """Return True when `if X not in sys.path:` would guard a then-branch insert.

    Only `ast.NotIn` is accepted: `_scope_has_guard_for_insert` walks the
    then-branch (`each_statement.body`) for the insert, so accepting `ast.In`
    here would silently approve `if X in sys.path: sys.path.insert(0, X)` —
    code that always inserts a duplicate. The else-branch is intentionally not
    inspected; a guard that places the insert in the else-branch of `if X in
    sys.path:` is unconventional and not supported.
    """
    if not isinstance(if_test_expression, ast.Compare):
        return False
    if len(if_test_expression.ops) != 1:
        return False
    if not isinstance(if_test_expression.ops[0], ast.NotIn):
        return False
    membership_target = if_test_expression.comparators[0]
    if not isinstance(membership_target, ast.Attribute) or membership_target.attr != "path":
        return False
    membership_receiver = membership_target.value
    return isinstance(membership_receiver, ast.Name) and membership_receiver.id == "sys"


def _scope_has_guard_for_insert(
    all_scope_statements: list[ast.stmt],
    insert_call_node: ast.Call,
) -> bool:
    for each_statement in all_scope_statements:
        if not isinstance(each_statement, ast.If):
            continue
        membership_test = each_statement.test
        if not isinstance(membership_test, ast.Compare):
            continue
        if not _is_sys_path_membership_if_test(membership_test):
            continue
        for each_inner in each_statement.body:
            if isinstance(each_inner, ast.Expr) and each_inner.value is insert_call_node:
                if len(insert_call_node.args) < SYS_PATH_INSERT_MINIMUM_ARGUMENT_COUNT:
                    return True
                if ast.dump(membership_test.left) == ast.dump(insert_call_node.args[1]):
                    return True
    return False


def _enclosing_scope_body(
    insert_call_node: ast.Call,
    parent_by_node_id: dict[int, ast.AST],
) -> list[ast.stmt]:
    parent = parent_by_node_id.get(id(insert_call_node))
    while parent is not None:
        if isinstance(parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return list(parent.body)
        parent = parent_by_node_id.get(id(parent))
    return []


def check_sys_path_insert_deduplication_guard(content: str, file_path: str) -> list[str]:
    """Flag sys.path.insert calls that lack a `not in sys.path` guard.

    Repeated module reloads can push the same entry onto sys.path multiple
    times when the call is unguarded. The repo convention is to wrap the
    call with `if <path> not in sys.path:`. The grant and revoke project
    permission scripts (grant_project_claude_permissions.py,
    revoke_project_claude_permissions.py) bypassed the convention.
    """
    if is_test_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    parent_by_node_id = _build_parent_map(tree)
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        if not _is_sys_path_insert_call(each_node):
            continue
        all_scope_statements = _enclosing_scope_body(each_node, parent_by_node_id)
        if _scope_has_guard_for_insert(all_scope_statements, each_node):
            continue
        issues.append(
            f"Line {each_node.lineno}: unguarded sys.path.insert"
            f" — {SYS_PATH_INSERT_GUIDANCE}"
        )
        if len(issues) >= MAX_SYS_PATH_INSERT_ISSUES:
            break
    return issues
