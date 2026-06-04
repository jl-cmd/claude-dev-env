"""Shared file classifiers, AST-walk helpers, and diff-scoping utilities for the code-rules checks."""

import ast
import difflib
import sys
from collections.abc import Iterator
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_DIFF_CHANGED_OPCODE_TAGS,
    ALL_HOOK_INFRASTRUCTURE_PATTERNS,
    ALL_MIGRATION_PATH_PATTERNS,
    ALL_TEST_PATH_PATTERNS,
    ALL_WORKFLOW_REGISTRY_PATTERNS,
)
from hooks_constants.unused_module_import_constants import (  # noqa: E402
    TYPE_CHECKING_IDENTIFIER,
)


def get_file_extension(file_path: str) -> str:
    """Extract lowercase file extension."""
    dot_index = file_path.rfind(".")
    if dot_index == -1:
        return ""
    return file_path[dot_index:].lower()


def is_hook_infrastructure(file_path: str) -> bool:
    """Check if file is a Claude Code hook (standalone infrastructure, not project code)."""
    path_lower = "/" + file_path.lower().replace("\\", "/").lstrip("/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in ALL_HOOK_INFRASTRUCTURE_PATTERNS)


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file."""
    path_lower = file_path.lower()
    basename_lower = path_lower.replace("\\", "/").rsplit("/", 1)[-1]
    if basename_lower == "conftest.py":
        return True
    return any(pattern in path_lower for pattern in ALL_TEST_PATH_PATTERNS)


def is_workflow_registry_file(file_path: str) -> bool:
    """Check if file is a workflow state/module registry file.

    Workflow tab files and state/module registry files use UPPER_SNAKE naming
    for StateDefinition and WorkflowModule instances by architectural convention.
    These are module-level singletons, not misplaced literal constants.
    """
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in ALL_WORKFLOW_REGISTRY_PATTERNS)


def is_spec_file(file_path: str) -> bool:
    """Check if file is an E2E spec file."""
    return ".spec." in file_path.lower()


def _is_type_checking_guard(if_node: ast.If) -> bool:
    test_node = if_node.test
    if isinstance(test_node, ast.Name) and test_node.id == TYPE_CHECKING_IDENTIFIER:
        return True
    return isinstance(test_node, ast.Attribute) and test_node.attr == TYPE_CHECKING_IDENTIFIER


def _walk_skipping_type_checking_blocks(node: ast.AST) -> "Iterator[ast.AST]":
    for each_child in ast.iter_child_nodes(node):
        if isinstance(each_child, ast.If) and _is_type_checking_guard(each_child):
            continue
        yield each_child
        yield from _walk_skipping_type_checking_blocks(each_child)


def _walk_skipping_nested_functions(node: ast.AST) -> "Iterator[ast.AST]":
    for each_child in ast.iter_child_nodes(node):
        if isinstance(each_child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield each_child
        yield from _walk_skipping_nested_functions(each_child)


def _walk_skipping_nested_function_defs(start_node: ast.AST) -> Iterator[ast.AST]:
    if isinstance(start_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return
    nodes_to_visit: list[ast.AST] = [start_node]
    while nodes_to_visit:
        current_node = nodes_to_visit.pop()
        yield current_node
        all_child_nodes = list(ast.iter_child_nodes(current_node))
        for each_child_node in reversed(all_child_nodes):
            if isinstance(each_child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            nodes_to_visit.append(each_child_node)


def _collect_annotated_arguments(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    """Return every argument node on a function that may carry an annotation."""
    arguments = function_node.args
    all_annotated_arguments: list[ast.arg] = []
    all_annotated_arguments.extend(arguments.posonlyargs)
    all_annotated_arguments.extend(arguments.args)
    all_annotated_arguments.extend(arguments.kwonlyargs)
    if arguments.vararg is not None:
        all_annotated_arguments.append(arguments.vararg)
    if arguments.kwarg is not None:
        all_annotated_arguments.append(arguments.kwarg)
    return all_annotated_arguments


def _collect_target_names(target: ast.expr) -> list[ast.Name]:
    """Return every ast.Name reachable through tuple/list/starred unpacking targets."""
    if isinstance(target, ast.Name):
        return [target]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[ast.Name] = []
        for each_element in target.elts:
            names.extend(_collect_target_names(each_element))
        return names
    if isinstance(target, ast.Starred):
        return _collect_target_names(target.value)
    return []


def _extract_fstring_literal_parts(
    joined_string_node: ast.JoinedStr,
    interpolation_placeholder: str = "INTERP",
) -> tuple[str, str]:
    """Return (display_body, shape_body) for an f-string node.

    ``display_body`` concatenates only the literal segments for use in the
    human-readable flag message. ``shape_body`` substitutes each interpolation
    slot with ``interpolation_placeholder`` so callers can choose a token that
    both preserves structural shape and does not collide with literal text in
    the source. The default ``"INTERP"`` keeps regex patterns for path shape
    (``\\w+/\\w+/\\w+``) matching across interpolation boundaries
    (e.g. ``/api/v1/{id}/home`` keeps its three path segments instead of
    collapsing to ``/api/v1//home``). Callers that will compare shape bodies
    verbatim — such as the skeleton builder — should pass their final token
    here directly rather than post-processing with ``.replace``, since that
    would corrupt literal text containing the default placeholder. Escaped
    braces (``{{`` / ``}}``) are already decoded by :mod:`ast` into their
    literal forms.
    """
    display_segments: list[str] = []
    shape_segments: list[str] = []
    for each_part in joined_string_node.values:
        if isinstance(each_part, ast.Constant) and isinstance(each_part.value, str):
            display_segments.append(each_part.value)
            shape_segments.append(each_part.value)
        else:
            shape_segments.append(interpolation_placeholder)
    return "".join(display_segments), "".join(shape_segments)


def is_migration_file(file_path: str) -> bool:
    """Check if file is a Django migration (must be self-contained)."""
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in ALL_MIGRATION_PATH_PATTERNS)


def _build_parent_map(module_tree: ast.Module) -> dict[int, ast.AST]:
    """Map child node id() to its parent node for ancestor walking."""
    parent_by_child_id: dict[int, ast.AST] = {}
    for each_parent in ast.walk(module_tree):
        for each_child in ast.iter_child_nodes(each_parent):
            parent_by_child_id[id(each_child)] = each_parent
    return parent_by_child_id


def _statement_is_docstring(statement_node: ast.stmt) -> bool:
    return (
        isinstance(statement_node, ast.Expr)
        and isinstance(statement_node.value, ast.Constant)
        and isinstance(statement_node.value.value, str)
    )


def _function_definition_line_span(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    end_lineno = getattr(function_node, "end_lineno", None) or function_node.lineno
    return end_lineno - function_node.lineno + 1


def _definition_docstring_line_span(
    definition_node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> int:
    """Return the source-line count of the definition's leading docstring.

    The Google Python Style Guide pairs a small-function preference that
    targets executable complexity with a requirement for complete docstrings
    on public functions and classes. Counting those docstring lines toward the
    function-length gate would penalize the very documentation the Guide
    mandates, so the gate measures executable span and excludes leading
    docstring statements.

    Args:
        definition_node: The function, method, or class definition node to
            inspect.

    Returns:
        The number of source lines the leading docstring statement occupies,
        or zero when the definition body is empty or does not open with a
        string literal.
    """
    definition_body = definition_node.body
    if not definition_body:
        return 0
    first_statement = definition_body[0]
    if _statement_is_docstring(first_statement):
        docstring_end = getattr(first_statement, "end_lineno", None) or first_statement.lineno
        return docstring_end - first_statement.lineno + 1
    return 0


def changed_line_numbers(prior_content: str, post_edit_content: str) -> set[int]:
    """Return the post-edit line numbers an edit added or replaced.

    Runs a line-level diff of *prior_content* against *post_edit_content* and
    collects the 1-indexed line numbers in *post_edit_content* that fall inside
    a ``replace`` or ``insert`` opcode. This mirrors the "added lines" notion
    that ``code_rules_gate.parse_added_line_numbers`` derives from
    ``git diff --unified=0``, so the PreToolUse layer and the gate agree on
    which lines the change touched.

    Args:
        prior_content: The file content before the edit.
        post_edit_content: The reconstructed file content after the edit.

    Returns:
        The set of 1-indexed line numbers in *post_edit_content* that the edit
        added or replaced.
    """
    matcher = difflib.SequenceMatcher(
        a=prior_content.splitlines(),
        b=post_edit_content.splitlines(),
        autojunk=False,
    )
    all_changed_lines: set[int] = set()
    for each_tag, _, _, each_post_start, each_post_end in matcher.get_opcodes():
        if each_tag in ALL_DIFF_CHANGED_OPCODE_TAGS:
            for each_post_index in range(each_post_start, each_post_end):
                all_changed_lines.add(each_post_index + 1)
    return all_changed_lines


def _scope_violations_to_changed_lines(
    all_violations_in_walk_order: list[tuple[range, str]],
    all_changed_lines: set[int] | None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Scope span-tagged violations by diff intersection.

    In-scope violations are always reported; the untouched out-of-scope set is
    surfaced or dropped according to which caller path is active:

    - ``defer_scope_to_caller`` True (the commit/push gate): every violation is
      returned in walk order so the gate's ``split_violations_by_scope`` can
      classify blocking vs advisory by added line. The gate does this scoping,
      so no scoping happens here.
    - ``all_changed_lines`` None (a terminal new-file or full-file write): every
      line was just authored, so every violation is in scope and returned.
    - ``all_changed_lines`` provided (a terminal diff-scoped Edit): only the
      in-scope violations whose span intersects the changed lines are returned;
      the untouched out-of-scope set is dropped, because untouched code must not
      block a single-file edit.

    Args:
        all_violations_in_walk_order: ``(span_range, issue_message)`` pairs in
            ``ast.walk`` traversal order, where ``span_range`` covers the
            violation's source lines.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat every violation as in-scope.
        defer_scope_to_caller: When True, return every violation message in walk
            order so the gate scopes by added line. When False, this enforcer is
            terminal and scopes directly.

    Returns:
        Every violation message when *defer_scope_to_caller* is True or
        *all_changed_lines* is None; otherwise only the in-scope messages whose
        span intersects the changed lines — so an edit that grows a function
        past the threshold always blocks even when many earlier untouched
        functions already exceed it.
    """
    if defer_scope_to_caller:
        return [each_message for _, each_message in all_violations_in_walk_order]
    if all_changed_lines is None:
        return [each_message for _, each_message in all_violations_in_walk_order]
    return [
        each_message
        for each_span, each_message in all_violations_in_walk_order
        if any(each_line in all_changed_lines for each_line in each_span)
    ]
