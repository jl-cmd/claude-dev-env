"""Parameter-annotation, return-annotation, and function-length checks."""

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
    _collect_annotated_arguments,
    _definition_docstring_line_span,
    _function_definition_line_span,
    _scope_violations_to_changed_lines,
    is_hook_infrastructure,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_SELF_AND_CLS_PARAMETER_NAMES,
    FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX,
    FUNCTION_LENGTH_BLOCKING_THRESHOLD,
)


def check_parameter_annotations(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_arg in _collect_annotated_arguments(each_node):
            if each_arg.arg in ALL_SELF_AND_CLS_PARAMETER_NAMES:
                continue
            if each_arg.annotation is None:
                issues.append(
                    f"Line {each_arg.lineno}: parameter {each_arg.arg!r} on {each_node.name!r} missing type annotation (CODE_RULES §6)"
                )
    return issues


def check_return_annotations(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if each_node.returns is None:
            issues.append(
                f"Line {each_node.lineno}: function {each_node.name!r} missing return type annotation (CODE_RULES §6)"
            )
    return issues


def check_function_length(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag functions whose executable span exceeds cognitive-load thresholds.

    Function executable spans — the definition span (signature line through
    last body statement, inclusive) minus the leading docstring lines of the
    function and of every function or class nested within it, per
    ``_definition_docstring_line_span`` summed over the nested definitions —
    at or above ``FUNCTION_LENGTH_BLOCKING_THRESHOLD`` appear in
    the returned issues list and block the write at the
    gate. The threshold rests on the small-function guidance in Robert C.
    Martin, *Clean Code* Chapter Three ("Functions") and the Google Python Style
    Guide's ~forty-line function review hint
    (https://google.github.io/styleguide/pyguide.html) — a measure of
    executable complexity, paired with the Guide's complete-docstring mandate
    for public APIs, so documentation lines never count against the gate; this
    gate blocks on body growth that pushes a function past that span. It does
    not derive from CODE_RULES file-length guidance, which governs advisory
    file-length signals and argues against hard numeric blocks.

    The issue message carries ``Function NAME (defined at line X) is Y lines``
    precisely so the gate's ``function_length_span_range`` can recover the
    function's full declared span (lines ``X`` through ``X + Y - 1``). The
    gate classifies the violation blocking when that span intersects the
    diff's added lines — the body grew this diff — and advisory otherwise — a
    pre-existing, untouched long function in a file the diff happened to
    touch. Anchoring to the span rather than a single ``Line N:`` definition
    line lets body growth on any interior line block correctly even when the
    ``def`` line itself is untouched.

    Exempt: test files (test bodies are sometimes long by necessity), Django
    migrations (auto-generated), workflow registries (registry entries), and
    hook infrastructure.

    Args:
        content: The Python source to analyze.
        file_path: The path of the file being checked.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when the function's declared span intersects the changed
            lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line and report the in-scope set.

    Returns:
        Blocking issues. When *defer_scope_to_caller* is True every violation is
        returned for the gate to scope; otherwise every violation in scope is
        returned.
    """
    if is_test_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_node in ast.walk(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        line_span = _function_definition_line_span(each_node)
        if line_span < FUNCTION_LENGTH_BLOCKING_THRESHOLD:
            continue
        docstring_line_total = sum(
            _definition_docstring_line_span(each_definition)
            for each_definition in ast.walk(each_node)
            if isinstance(
                each_definition, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
        )
        executable_line_span = line_span - docstring_line_total
        if executable_line_span >= FUNCTION_LENGTH_BLOCKING_THRESHOLD:
            span_range = range(each_node.lineno, each_node.lineno + line_span)
            message = (
                f"Function {each_node.name!r} (defined at line {each_node.lineno}) "
                f"is {line_span} lines - {FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX}"
            )
            all_violations_in_walk_order.append((span_range, message))
    return _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
