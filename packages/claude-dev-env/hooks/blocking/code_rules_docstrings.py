"""Google-style docstring presence and docstring Args-versus-signature checks."""

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
    _statement_is_docstring,
    _walk_skipping_nested_functions,
    _walk_skipping_type_checking_blocks,
    is_hook_infrastructure,
    is_test_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_DOCSTRING_EXCLUSIVE_SCOPE_PHRASES,
    ALL_DOCSTRING_EXEMPT_DECORATOR_NAMES,
    ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES,
    ALL_DOCSTRING_MULTIPLE_CONDITION_JOINING_PHRASES,
    DOCSTRING_FALLBACK_BRANCH_MINIMUM_ROUTE_COUNT,
    DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT,
    MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES,
    MAX_DOCSTRING_FALLBACK_BRANCH_ISSUES,
    MAX_DOCSTRING_FORMAT_ISSUES,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_DOCSTRING_ARGS_SECTION_HEADERS,
    ALL_DOCSTRING_TERMINATING_SECTION_HEADERS,
    ALL_SELF_AND_CLS_PARAMETER_NAMES,
    DOCSTRING_ARG_ENTRY_PATTERN,
)


def _function_is_private_or_dunder(function_name: str) -> bool:
    if function_name.startswith("__") and function_name.endswith("__"):
        return True
    return function_name.startswith("_")


def _decorator_label(decorator_node: ast.expr) -> str:
    if isinstance(decorator_node, ast.Name):
        return decorator_node.id
    if isinstance(decorator_node, ast.Attribute):
        prefix = (
            decorator_node.value.id
            if isinstance(decorator_node.value, ast.Name)
            else ""
        )
        return f"{prefix}.{decorator_node.attr}" if prefix else decorator_node.attr
    if isinstance(decorator_node, ast.Call):
        return _decorator_label(decorator_node.func)
    return ""


def _function_has_exempt_decorator(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    for each_decorator in function_node.decorator_list:
        if _decorator_label(each_decorator) in ALL_DOCSTRING_EXEMPT_DECORATOR_NAMES:
            return True
    return False


def _function_body_line_count(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    if not function_node.body:
        return 0
    first_body_index = 0
    if _statement_is_docstring(function_node.body[0]):
        if len(function_node.body) == 1:
            return 0
        first_body_index = 1
    last_statement = function_node.body[-1]
    end_line = getattr(last_statement, "end_lineno", last_statement.lineno)
    first_line = function_node.body[first_body_index].lineno
    return max(0, end_line - first_line + 1)


def _function_documentable_parameter_count(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    documentable_count = 0
    for each_argument in function_node.args.args:
        if each_argument.arg in ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES:
            continue
        documentable_count += 1
    documentable_count += len(function_node.args.kwonlyargs)
    for each_argument in function_node.args.posonlyargs:
        if each_argument.arg in ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES:
            continue
        documentable_count += 1
    if function_node.args.vararg is not None:
        documentable_count += 1
    if function_node.args.kwarg is not None:
        documentable_count += 1
    return documentable_count


def _annotation_is_explicit_none_return(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Constant) and annotation_node.value is None:
        return True
    return isinstance(annotation_node, ast.Name) and annotation_node.id == "None"


def _annotation_is_noreturn(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Name) and annotation_node.id == "NoReturn":
        return True
    return isinstance(annotation_node, ast.Attribute) and annotation_node.attr == "NoReturn"


def _function_body_contains_raise(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return any(
        isinstance(each_descendant, ast.Raise)
        for each_descendant in _walk_skipping_nested_functions(function_node)
    )


def _function_body_contains_yield(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return any(
        isinstance(each_descendant, (ast.Yield, ast.YieldFrom))
        for each_descendant in _walk_skipping_nested_functions(function_node)
    )


def _function_docstring_text(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    docstring_value = ast.get_docstring(function_node)
    return docstring_value or ""


def _missing_docstring_sections(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    docstring_text = _function_docstring_text(function_node)
    documentable_parameter_count = _function_documentable_parameter_count(function_node)
    has_non_none_return = (
        function_node.returns is not None
        and not _annotation_is_explicit_none_return(function_node.returns)
        and not _annotation_is_noreturn(function_node.returns)
    )
    has_raise_statement = _function_body_contains_raise(function_node)
    has_yield_statement = _function_body_contains_yield(function_node)
    missing_sections: list[str] = []
    if documentable_parameter_count > 0 and "Args:" not in docstring_text:
        missing_sections.append("Args:")
    if has_non_none_return and not (
        "Returns:" in docstring_text or "Yields:" in docstring_text
    ):
        section_label = "Yields:" if has_yield_statement else "Returns:"
        missing_sections.append(section_label)
    if has_raise_statement and "Raises:" not in docstring_text:
        missing_sections.append("Raises:")
    return missing_sections


def check_docstring_format(content: str, file_path: str) -> list[str]:
    """Flag public functions missing required Google-style docstring sections.

    A public function whose signature has documentable parameters, returns
    a non-None value, or raises must have the matching `Args:` / `Returns:`
    (or `Yields:`) / `Raises:` sections so callers can read the contract
    without scanning the body.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_private_or_dunder(each_node.name):
            continue
        if _function_has_exempt_decorator(each_node):
            continue
        if _function_body_line_count(each_node) <= DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT:
            continue
        missing_sections = _missing_docstring_sections(each_node)
        if not missing_sections:
            continue
        issues.append(
            f"Line {each_node.lineno}: {each_node.name}() docstring missing required "
            f"section(s): {', '.join(missing_sections)} — Google style required for public APIs"
        )
        if len(issues) >= MAX_DOCSTRING_FORMAT_ISSUES:
            break
    return issues[:MAX_DOCSTRING_FORMAT_ISSUES]


def _signature_parameter_names(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    arguments = function_node.args
    real_names: set[str] = set()
    for each_argument in arguments.posonlyargs + arguments.args + arguments.kwonlyargs:
        real_names.add(each_argument.arg)
    if arguments.vararg is not None:
        real_names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        real_names.add(arguments.kwarg.arg)
    return real_names - ALL_SELF_AND_CLS_PARAMETER_NAMES


def _is_docstring_terminating_section_header(stripped_line: str) -> bool:
    return stripped_line in ALL_DOCSTRING_TERMINATING_SECTION_HEADERS


def _documented_argument_names(docstring_text: str) -> list[str]:
    docstring_lines = docstring_text.splitlines()
    args_section_index = _find_args_section_index(docstring_lines)
    if args_section_index is None:
        return []
    documented_names: list[str] = []
    entry_indent: int | None = None
    for each_line in docstring_lines[args_section_index + 1:]:
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        if _is_docstring_terminating_section_header(stripped_line):
            break
        current_indent = len(each_line) - len(each_line.lstrip())
        if current_indent == 0:
            break
        if entry_indent is None:
            entry_indent = current_indent
        if current_indent > entry_indent:
            continue
        entry_match = DOCSTRING_ARG_ENTRY_PATTERN.match(stripped_line)
        if entry_match is not None:
            documented_names.append(entry_match.group(1))
    return documented_names


def _find_args_section_index(all_docstring_lines: list[str]) -> int | None:
    for each_line_index, each_line in enumerate(all_docstring_lines):
        if each_line.strip() in ALL_DOCSTRING_ARGS_SECTION_HEADERS:
            return each_line_index
    return None


def check_docstring_args_match_signature(content: str, file_path: str) -> list[str]:
    """Flag docstring Args: entries naming a parameter the signature lacks.

    A fix that renames a parameter often leaves the adjacent ``Args:`` line
    stale. Each documented argument name is compared to the real signature;
    a documented name with no matching parameter is reported. Only the
    ``Args:`` section is validated — ``Raises:`` is left alone because
    callee-propagated exceptions cause false positives. Functions that
    accept ``**kwargs`` are skipped because their documented names may be
    keyword keys the signature cannot enumerate.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per stale documented argument, capped at the module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_private_or_dunder(each_node.name):
            continue
        if _function_has_exempt_decorator(each_node):
            continue
        if _function_body_line_count(each_node) <= DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT:
            continue
        if each_node.args.kwarg is not None:
            continue
        documented_names = _documented_argument_names(_function_docstring_text(each_node))
        if not documented_names:
            continue
        real_names = _signature_parameter_names(each_node)
        for each_documented_name in documented_names:
            if each_documented_name in real_names:
                continue
            issues.append(
                f"Line {each_node.lineno}: {each_node.name}() docstring Args: lists "
                f"'{each_documented_name}' which is not a parameter - update the "
                "docstring to match the signature"
            )
            if len(issues) >= MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES:
                return issues[:MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES]
    return issues[:MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES]


def _callee_expression_name(expression: ast.expr) -> str:
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        receiver_name = _callee_expression_name(expression.value)
        if not receiver_name:
            return ast.unparse(expression)
        return f"{receiver_name}.{expression.attr}"
    return ""


def _call_callee_name(call_node: ast.Call) -> str:
    return _callee_expression_name(call_node.func)


def _branch_routes_directly_to_call(branch_node: ast.If) -> str:
    """Return the callee name an early-return guard routes to, or empty string.

    A guard counts when its block contains exactly one call expression and then
    returns. A second call expression disqualifies the block; non-call
    statements such as an assignment or a loop are skipped and do not
    disqualify it. The await wrapper around an async call is unwrapped first.
    """
    routed_callee = ""
    saw_return = False
    for each_statement in branch_node.body:
        candidate_expression: ast.expr | None = None
        if isinstance(each_statement, ast.Expr):
            candidate_expression = each_statement.value
        elif isinstance(each_statement, ast.Return):
            saw_return = True
            continue
        if candidate_expression is None:
            continue
        if isinstance(candidate_expression, ast.Await):
            candidate_expression = candidate_expression.value
        if not isinstance(candidate_expression, ast.Call):
            return ""
        if routed_callee:
            return ""
        routed_callee = _call_callee_name(candidate_expression)
    if not saw_return:
        return ""
    return routed_callee


def _shared_fallback_route_count(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[str, int]:
    route_count_by_callee: dict[str, int] = {}
    for each_statement in function_node.body:
        if not isinstance(each_statement, ast.If):
            continue
        routed_callee = _branch_routes_directly_to_call(each_statement)
        if not routed_callee:
            continue
        route_count_by_callee[routed_callee] = (
            route_count_by_callee.get(routed_callee, 0) + 1
        )
    if not route_count_by_callee:
        return "", 0
    busiest_callee = max(route_count_by_callee, key=lambda name: route_count_by_callee[name])
    return busiest_callee, route_count_by_callee[busiest_callee]


def _summary_contains_phrase_at_word_boundary(summary_text: str, phrase: str) -> bool:
    search_start = 0
    while True:
        match_index = summary_text.find(phrase, search_start)
        if match_index == -1:
            return False
        preceding_is_boundary = (
            match_index == 0 or not summary_text[match_index - 1].isalnum()
        )
        following_index = match_index + len(phrase)
        following_is_boundary = (
            following_index >= len(summary_text)
            or not summary_text[following_index].isalnum()
        )
        if preceding_is_boundary and following_is_boundary:
            return True
        search_start = match_index + 1


def _summary_joins_multiple_conditions(summary_text: str) -> bool:
    return any(
        joining_phrase in summary_text
        for joining_phrase in ALL_DOCSTRING_MULTIPLE_CONDITION_JOINING_PHRASES
    )


def _docstring_summary_scopes_a_single_condition(docstring_text: str) -> bool:
    summary_text = docstring_text.split("\n\n", 1)[0].lower()
    has_scope_phrase = any(
        _summary_contains_phrase_at_word_boundary(summary_text, each_phrase)
        for each_phrase in ALL_DOCSTRING_EXCLUSIVE_SCOPE_PHRASES
    )
    if not has_scope_phrase:
        return False
    return not _summary_joins_multiple_conditions(summary_text)


def check_docstring_fallback_branch_coverage(content: str, file_path: str) -> list[str]:
    """Flag a fallback docstring that scopes a branch the body reaches twice.

    The drift this catches: a function whose summary describes a fallback
    action under a single condition (``only when``, ``falls back to ... when``)
    while the body routes to that same fallback call from two or more distinct
    early-return guards. The second guard fires under a condition the prose
    never names, so the enumeration the reader trusts is incomplete. This is
    the deterministic slice of Category O6 (docstring prose vs implementation
    drift): a structural branch-count-versus-prose-condition mismatch.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per function whose fallback prose omits a second route to the
        same call, capped at the module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_has_exempt_decorator(each_node):
            continue
        docstring_text = _function_docstring_text(each_node)
        if not docstring_text:
            continue
        if not _docstring_summary_scopes_a_single_condition(docstring_text):
            continue
        fallback_callee, route_count = _shared_fallback_route_count(each_node)
        if route_count < DOCSTRING_FALLBACK_BRANCH_MINIMUM_ROUTE_COUNT:
            continue
        issues.append(
            f"Line {each_node.lineno}: {each_node.name}() docstring scopes a fallback to "
            f"one condition, but the body routes to {fallback_callee}() from {route_count} "
            "distinct branches — enumerate every condition that reaches the fallback "
            "(Category O6 docstring-vs-implementation drift)"
        )
        if len(issues) >= MAX_DOCSTRING_FALLBACK_BRANCH_ISSUES:
            break
    return issues[:MAX_DOCSTRING_FALLBACK_BRANCH_ISSUES]
