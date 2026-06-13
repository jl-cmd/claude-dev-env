#!/usr/bin/env python3
"""Blocking hook: a named subprocess-budget helper must account for every reachable subprocess timeout.

Fires when a Write/Edit produces a Python module that both:

  * defines a function whose name names a worst-case or budget total
    (a marker ``worst_case``, ``_budget``, or ``budget_seconds`` aligns with the
    start or end of the function name's underscore-delimited tokens, so an
    interior ``budget`` segment such as ``audit_budget_report`` does not qualify),
    and
  * passes ``timeout=`` (an integer literal or a module-level integer
    constant) to one or more subprocess ``run`` calls, recognized in both the
    ``subprocess.run(...)`` attribute form and the bare ``run(...)`` form bound
    by ``from subprocess import run`` (including an aliased import),

but the budget total omits a distinct subprocess timeout value reachable in one
invocation. The reachable set is the subprocess timeouts in functions the module
``main`` entry point transitively calls; a module with no ``main`` treats every
function as reachable. The budget total counts only the integer values that flow
into the helper's ``return`` expression — its returned literals, the module
constants it references there, and the local names bound to integers it returns
— so a stray literal elsewhere in the helper body never masks an omitted timeout.
A budget helper that undercounts a reachable subprocess timeout reports a
wall-clock margin wider than the real one, so a later change can silently cross
the harness timeout while the named guard still reads green.

Test files are exempt: the gate skips paths matching the project's test-path
patterns so a test module can stage undercounting fixtures freely.
"""

import ast
import json
import sys
from pathlib import Path

FunctionDefinition = ast.FunctionDef | ast.AsyncFunctionDef

_blocking_dir = str(Path(__file__).resolve().parent)
_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _blocking_dir not in sys.path:
    sys.path.insert(0, _blocking_dir)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from code_rules_shared import is_test_file  # noqa: E402

from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.subprocess_budget_completeness_constants import (  # noqa: E402
    ALL_BUDGET_NAME_MARKERS,
    BUDGET_ENTRY_POINT_FUNCTION_NAME,
    SUBPROCESS_TIMEOUT_KEYWORD,
)
from hooks_constants.windows_rmtree_blocker_constants import (  # noqa: E402
    PYTHON_FILE_EXTENSION,
)


def is_python_target(file_path: str) -> bool:
    return file_path.endswith(PYTHON_FILE_EXTENSION)


def resolved_content(all_tool_input_fields: dict[str, object]) -> str:
    written_content = all_tool_input_fields.get("content")
    if isinstance(written_content, str):
        return written_content
    return reconstructed_edit_content(all_tool_input_fields)


def reconstructed_edit_content(all_tool_input_fields: dict[str, object]) -> str:
    file_path = all_tool_input_fields.get("file_path")
    old_string = all_tool_input_fields.get("old_string")
    new_string = all_tool_input_fields.get("new_string")
    if not isinstance(file_path, str) or not isinstance(old_string, str):
        return ""
    if not isinstance(new_string, str) or not old_string:
        return ""
    existing_content = existing_file_content(file_path)
    if existing_content is None or old_string not in existing_content:
        return ""
    return existing_content.replace(old_string, new_string, 1)


def existing_file_content(file_path: str) -> str | None:
    try:
        with open(file_path, "r", encoding="utf-8") as existing_file:
            return existing_file.read()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None


def integer_literal_value(node: ast.expr) -> int | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    ):
        return node.value
    return None


def resolved_integer_value(node: ast.expr, value_by_constant_name: dict[str, int]) -> int | None:
    literal_value = integer_literal_value(node)
    if literal_value is not None:
        return literal_value
    if isinstance(node, ast.Name):
        return value_by_constant_name.get(node.id)
    return None


def collect_reachable_subprocess_timeout_values(
    tree: ast.Module,
    value_by_constant_name: dict[str, int],
    all_reachable_function_names: set[str] | None,
    all_bare_run_aliases: set[str],
) -> set[int]:
    all_timeout_values: set[int] = set()
    for each_function in iter_function_definitions(tree):
        if (
            all_reachable_function_names is not None
            and each_function.name not in all_reachable_function_names
        ):
            continue
        all_timeout_values |= subprocess_timeout_values_in_function(
            each_function, value_by_constant_name, all_bare_run_aliases
        )
    return all_timeout_values


def subprocess_timeout_values_in_function(
    function_node: FunctionDefinition,
    value_by_constant_name: dict[str, int],
    all_bare_run_aliases: set[str],
) -> set[int]:
    all_timeout_values: set[int] = set()
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.Call):
            continue
        if not is_subprocess_run_call(each_node, all_bare_run_aliases):
            continue
        for each_keyword in each_node.keywords:
            if each_keyword.arg != SUBPROCESS_TIMEOUT_KEYWORD:
                continue
            timeout_value = resolved_integer_value(each_keyword.value, value_by_constant_name)
            if timeout_value is not None:
                all_timeout_values.add(timeout_value)
    return all_timeout_values


def iter_function_definitions(tree: ast.Module) -> list[FunctionDefinition]:
    return [
        each_node
        for each_node in ast.walk(tree)
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def callees_by_function_name(tree: ast.Module) -> dict[str, set[str]]:
    callee_names_by_caller: dict[str, set[str]] = {}
    for each_function in iter_function_definitions(tree):
        callee_names_by_caller[each_function.name] = called_function_names(each_function)
    return callee_names_by_caller


def called_function_names(function_node: FunctionDefinition) -> set[str]:
    all_called_names: set[str] = set()
    for each_node in ast.walk(function_node):
        if isinstance(each_node, ast.Call) and isinstance(each_node.func, ast.Name):
            all_called_names.add(each_node.func.id)
    return all_called_names


def reachable_function_names_from_entry_points(tree: ast.Module) -> set[str] | None:
    callee_names_by_caller = callees_by_function_name(tree)
    if BUDGET_ENTRY_POINT_FUNCTION_NAME not in callee_names_by_caller:
        return None
    reachable_names: set[str] = set()
    pending_names = [BUDGET_ENTRY_POINT_FUNCTION_NAME]
    while pending_names:
        current_name = pending_names.pop()
        if current_name in reachable_names:
            continue
        reachable_names.add(current_name)
        pending_names.extend(callee_names_by_caller.get(current_name, set()))
    return reachable_names


def is_subprocess_run_call(call_node: ast.Call, all_bare_run_aliases: set[str]) -> bool:
    function_node = call_node.func
    if isinstance(function_node, ast.Attribute):
        return function_node.attr == "run" and _attribute_root_name(function_node) == "subprocess"
    if isinstance(function_node, ast.Name):
        return function_node.id in all_bare_run_aliases
    return False


def _attribute_root_name(attribute_node: ast.Attribute) -> str | None:
    base_node = attribute_node.value
    if isinstance(base_node, ast.Name):
        return base_node.id
    return None


def bare_run_aliases(tree: ast.Module) -> set[str]:
    all_aliases: set[str] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.ImportFrom) or each_node.module != "subprocess":
            continue
        for each_name in each_node.names:
            if each_name.name == "run":
                all_aliases.add(each_name.asname or each_name.name)
    return all_aliases


def values_flowing_into_returned_total(
    function_node: FunctionDefinition, value_by_constant_name: dict[str, int]
) -> set[int]:
    value_by_local_name = local_integer_bindings(function_node, value_by_constant_name)
    all_accounted_values: set[int] = set()
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.Return) or each_node.value is None:
            continue
        all_accounted_values |= integer_values_in_expression(
            each_node.value, value_by_local_name, value_by_constant_name
        )
    return all_accounted_values


def local_integer_bindings(
    function_node: FunctionDefinition, value_by_constant_name: dict[str, int]
) -> dict[str, int]:
    value_by_local_name: dict[str, int] = {}
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.Assign):
            continue
        bound_value = resolved_integer_value(each_node.value, value_by_constant_name)
        if bound_value is None:
            continue
        for each_target in each_node.targets:
            if isinstance(each_target, ast.Name):
                value_by_local_name[each_target.id] = bound_value
    return value_by_local_name


def integer_values_in_expression(
    expression_node: ast.expr,
    value_by_local_name: dict[str, int],
    value_by_constant_name: dict[str, int],
) -> set[int]:
    all_values: set[int] = set()
    for each_node in ast.walk(expression_node):
        literal_value = integer_literal_value(each_node) if isinstance(each_node, ast.expr) else None
        if literal_value is not None:
            all_values.add(literal_value)
        elif isinstance(each_node, ast.Name):
            named_value = value_by_local_name.get(each_node.id, value_by_constant_name.get(each_node.id))
            if named_value is not None:
                all_values.add(named_value)
    return all_values


def is_budget_function(function_node: FunctionDefinition) -> bool:
    all_name_tokens = underscore_tokens(function_node.name.lower())
    return any(
        marker_anchored_to_name_boundary(underscore_tokens(each_marker), all_name_tokens)
        for each_marker in ALL_BUDGET_NAME_MARKERS
    )


def underscore_tokens(snake_case_name: str) -> list[str]:
    return [each_segment for each_segment in snake_case_name.split("_") if each_segment]


def marker_anchored_to_name_boundary(
    all_marker_tokens: list[str], all_name_tokens: list[str]
) -> bool:
    if not all_marker_tokens or len(all_marker_tokens) > len(all_name_tokens):
        return False
    starts_with_marker = all_name_tokens[: len(all_marker_tokens)] == all_marker_tokens
    ends_with_marker = all_name_tokens[-len(all_marker_tokens) :] == all_marker_tokens
    return starts_with_marker or ends_with_marker


def find_undercounted_budget(content: str) -> tuple[str, set[int]] | None:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    referenced_constants = collect_module_constant_values(tree)
    all_reachable_function_names = reachable_function_names_from_entry_points(tree)
    all_bare_run_aliases = bare_run_aliases(tree)
    subprocess_timeout_values = collect_reachable_subprocess_timeout_values(
        tree, referenced_constants, all_reachable_function_names, all_bare_run_aliases
    )
    if not subprocess_timeout_values:
        return None

    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not is_budget_function(each_node):
            continue
        accounted_values = values_flowing_into_returned_total(each_node, referenced_constants)
        omitted_values = subprocess_timeout_values - accounted_values
        if omitted_values:
            return each_node.name, omitted_values
    return None


def collect_module_constant_values(tree: ast.Module) -> dict[str, int]:
    value_by_constant_name: dict[str, int] = {}
    for each_node in tree.body:
        if isinstance(each_node, ast.Assign):
            assigned_value = integer_literal_value(each_node.value)
            if assigned_value is None:
                continue
            for each_target in each_node.targets:
                if isinstance(each_target, ast.Name):
                    value_by_constant_name[each_target.id] = assigned_value
        elif isinstance(each_node, ast.AnnAssign) and each_node.value is not None:
            annotated_value = integer_literal_value(each_node.value)
            if annotated_value is not None and isinstance(each_node.target, ast.Name):
                value_by_constant_name[each_node.target.id] = annotated_value
    return value_by_constant_name


def format_block_message(file_path: str, function_name: str, all_omitted_values: set[int]) -> str:
    omitted_text = ", ".join(f"{each_value}s" for each_value in sorted(all_omitted_values))
    return (
        f"SUBPROCESS BUDGET INCOMPLETE: {function_name}() in {file_path} sums a subset of the "
        f"subprocess timeouts reachable in one invocation and omits timeout value(s) {omitted_text} that "
        "one invocation can reach. A named worst-case/budget helper must account for every subprocess timeout reachable "
        "in a single invocation, so its reported margin against the harness timeout is real. Either add the "
        f"omitted timeout(s) to the modeled total, or rename the helper to name the phases it actually covers "
        "and document the residual full-invocation margin separately."
    )


def main() -> None:
    hook_input = read_hook_input_dictionary_from_stdin()
    if hook_input is None:
        sys.exit(0)

    raw_tool_input = hook_input.get("tool_input", {})
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path or not is_python_target(file_path):
        sys.exit(0)
    if is_test_file(file_path):
        sys.exit(0)

    content = resolved_content(tool_input)
    if not content:
        sys.exit(0)

    undercounted_budget = find_undercounted_budget(content)
    if undercounted_budget is None:
        sys.exit(0)

    function_name, omitted_values = undercounted_budget
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": format_block_message(
                        file_path, function_name, omitted_values
                    ),
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
