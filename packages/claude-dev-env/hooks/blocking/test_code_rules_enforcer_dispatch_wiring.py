"""Meta-test asserting every check_* function is reachable from the full gate.

The per-check test modules each prove one ``check_*`` function flags the right
violation, but none proves the enforcer actually calls that function. A refactor
that drops a dispatch line from ``validate_content_for_full_gate`` or from one
of its extension-issue helper functions leaves every per-check test green
while the check stops firing at Write/Edit time — the precise failure mode
that would let a dead module-level constant (the ``MEDIUM_TEXT`` class) or an
orphan CSS class slip past the gate again.

::

    validate_content_for_full_gate -> _python_extension_issues -> _python_magic_value_and_constant_issues
                                                                        |
                                                                        v
                                                            references check_magic_values
    -> check_magic_values counts as reachable

    check_unanchored_command_dispatch: called only from
    _hook_infrastructure_blocking_issues, which the full gate's call graph
    never reaches -> stays in KNOWN_UNDISPATCHED_CHECKS

This module walks the enforcer's real call graph from
``validate_content_for_full_gate``, following every direct function call into
the functions the enforcer module defines, and collects every
``check_*``/``advise_*`` name each reached function body references — a direct
call or a bare reference passed on as a callback (the
``_fragment_or_deferred_check(check_magic_values, ...)`` shape). A name that
surfaces only in an import statement or a docstring is not a reference inside
a reached function body, so it does not count; this is what keeps the check
from going vacuous the way a whole-module substring scan would.

A check that is intentionally not wired must be listed in
``KNOWN_UNDISPATCHED_CHECKS`` with a reason in this docstring.
``check_unanchored_command_dispatch`` is listed there: it guards a
``hooks/blocking`` command classifier, and the whole
``validate_content_for_full_gate`` verdict stays off hook-infrastructure
files, so the enforcer dispatches it from
``_hook_infrastructure_blocking_issues`` instead. The companion
``test_code_rules_enforcer_cap_meta.py`` guards the payload-cap convention;
this module guards the wiring.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import pathlib
import sys

_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_specification = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIRECTORY / "code_rules_enforcer.py",
)
assert _hook_specification is not None
assert _hook_specification.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_specification)
_hook_specification.loader.exec_module(_hook_module)

KNOWN_UNDISPATCHED_CHECKS: frozenset[str] = frozenset(
    {"check_unanchored_command_dispatch"}
)

DISPATCH_ENTRY_POINT_NAME = "validate_content_for_full_gate"


def _all_check_function_names() -> list[str]:
    return [
        each_attribute_name
        for each_attribute_name in dir(_hook_module)
        if each_attribute_name.startswith("check_")
        and callable(getattr(_hook_module, each_attribute_name))
    ]


def _module_level_function_defs(module_tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """Map each module-level function's name to its definition node."""
    return {
        each_node.name: each_node
        for each_node in module_tree.body
        if isinstance(each_node, ast.FunctionDef)
    }


def _local_call_targets(function_node: ast.FunctionDef) -> set[str]:
    """Return the plain-name targets one function directly calls."""
    return {
        each_call.func.id
        for each_call in ast.walk(function_node)
        if isinstance(each_call, ast.Call) and isinstance(each_call.func, ast.Name)
    }


def _unvisited_local_calls(
    function_name: str,
    function_defs_by_name: dict[str, ast.FunctionDef],
    visited: set[str],
) -> list[str]:
    """Return *function_name*'s call targets not already visited by the walk."""
    function_node = function_defs_by_name.get(function_name)
    if function_node is None:
        return []
    return [each for each in _local_call_targets(function_node) if each not in visited]


def _reachable_function_names(
    start_name: str, function_defs_by_name: dict[str, ast.FunctionDef]
) -> set[str]:
    """Return every function name the call graph reaches, starting from start_name."""
    visited: set[str] = set()
    pending = [start_name]
    while pending:
        each_pending_name = pending.pop()
        if each_pending_name in visited:
            continue
        visited.add(each_pending_name)
        pending.extend(_unvisited_local_calls(each_pending_name, function_defs_by_name, visited))
    return visited


def _referenced_names(function_node: ast.FunctionDef) -> set[str]:
    """Return every loaded identifier one function body references.

    A callback-style dispatch (``_fragment_or_deferred_check(check_magic_values,
    ...)``) passes the check function by bare name rather than calling it
    directly, so this collects every loaded ``Name``, not only call targets.
    """
    return {
        each_name.id
        for each_name in ast.walk(function_node)
        if isinstance(each_name, ast.Name) and isinstance(each_name.ctx, ast.Load)
    }


def _reachable_referenced_names(
    start_name: str, function_defs_by_name: dict[str, ast.FunctionDef]
) -> set[str]:
    """Return every identifier referenced by a function the call graph reaches."""
    reachable_function_names = _reachable_function_names(start_name, function_defs_by_name)
    referenced_names: set[str] = set()
    for each_function_name in reachable_function_names:
        function_node = function_defs_by_name.get(each_function_name)
        if function_node is not None:
            referenced_names.update(_referenced_names(function_node))
    return referenced_names


def test_every_check_function_is_reachable_from_the_full_gate() -> None:
    module_tree = ast.parse(inspect.getsource(_hook_module))
    function_defs_by_name = _module_level_function_defs(module_tree)
    reachable_names = _reachable_referenced_names(DISPATCH_ENTRY_POINT_NAME, function_defs_by_name)
    all_check_names = set(_all_check_function_names())
    undispatched_check_names = all_check_names - reachable_names
    unexpected_undispatched = undispatched_check_names - KNOWN_UNDISPATCHED_CHECKS
    assert unexpected_undispatched == set(), (
        f"check_* functions are imported but never reachable from "
        f"validate_content_for_full_gate's call graph: {sorted(unexpected_undispatched)}. "
        f"Wire each into validate_content_for_phase or one of its extension-issue "
        f"helpers so the check fires at Write/Edit time, or list it in "
        f"KNOWN_UNDISPATCHED_CHECKS with a reason in the test header docstring."
    )


def test_known_undispatched_set_lists_only_existing_checks() -> None:
    all_check_names = set(_all_check_function_names())
    stale_names = KNOWN_UNDISPATCHED_CHECKS - all_check_names
    assert stale_names == set(), (
        f"KNOWN_UNDISPATCHED_CHECKS lists functions that no longer exist: "
        f"{sorted(stale_names)}. Restore the function or remove it from the set."
    )
