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
    is_strict_test_file,
    is_test_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_DOCSTRING_EXCLUSIVE_SCOPE_PHRASES,
    ALL_DOCSTRING_EXEMPT_DECORATOR_NAMES,
    ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES,
    ALL_DOCSTRING_MULTIPLE_CONDITION_JOINING_PHRASES,
    ALL_DOCSTRING_NO_CONSUMER_CLAIM_PHRASES,
    ALL_GENERIC_CHECK_NAME_TOKENS,
    DOCSTRING_FALLBACK_BRANCH_MINIMUM_ROUTE_COUNT,
    DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT,
    MAX_CLASS_DOCSTRING_PUBLIC_METHOD_ISSUES,
    MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES,
    MAX_DOCSTRING_FALLBACK_BRANCH_ISSUES,
    MAX_DOCSTRING_FORMAT_ISSUES,
    MAX_DOCSTRING_NO_CONSUMER_CLAIM_ISSUES,
    MAX_DOCSTRING_TUPLE_ENUMERATION_ISSUES,
    MAX_MODULE_DOCSTRING_CHECK_ROSTER_ISSUES,
    MINIMUM_PUBLIC_CHECKS_FOR_MODULE_DOCSTRING_ROSTER,
    MINIMUM_PUBLIC_METHODS_FOR_CLASS_DOCSTRING_BREADTH,
    MINIMUM_TUPLE_MEMBERS_FOR_DOCSTRING_ENUMERATION,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_DOCSTRING_ARGS_SECTION_HEADERS,
    ALL_DOCSTRING_TERMINATING_SECTION_HEADERS,
    ALL_SELF_AND_CLS_PARAMETER_NAMES,
    DOCSTRING_ARG_ENTRY_PATTERN,
    IDENTIFIER_SHAPED_TUPLE_MEMBER_PATTERN,
    INLINE_CODE_TOKEN_PATTERN,
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


def _class_docstring_summary_is_single_line(docstring_text: str) -> bool:
    stripped_text = docstring_text.strip()
    if not stripped_text:
        return False
    summary_line, separator, _remainder = stripped_text.partition("\n")
    if separator and stripped_text[len(summary_line):].strip():
        return False
    return bool(summary_line.strip())


def _public_method_names(class_node: ast.ClassDef) -> list[str]:
    deduplicated_names: dict[str, None] = {}
    for each_statement in class_node.body:
        if not isinstance(each_statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_private_or_dunder(each_statement.name):
            continue
        deduplicated_names[each_statement.name] = None
    return list(deduplicated_names)


def _name_tokens(method_name: str) -> list[str]:
    return [each_token for each_token in method_name.split("_") if each_token]


def _docstring_mentions_method(docstring_text: str, method_name: str) -> bool:
    lowered_docstring = docstring_text.lower()
    if method_name.lower() in lowered_docstring:
        return True
    return all(
        each_token.lower() in lowered_docstring for each_token in _name_tokens(method_name)
    )


def _unmentioned_public_methods(class_node: ast.ClassDef, docstring_text: str) -> list[str]:
    return [
        each_name
        for each_name in _public_method_names(class_node)
        if not _docstring_mentions_method(docstring_text, each_name)
    ]


def check_class_docstring_names_public_methods(
    content: str, file_path: str
) -> list[str]:
    """Flag a one-line class docstring that omits two or more public methods.

    A class whose docstring is a single summary line names one responsibility,
    so a reader trusts that line to describe the whole class. When the class
    later gains a second public entry point — the drift pattern where a
    coffee-break reporter grows a regular-pace method — the terse summary keeps
    describing only the original feature. Each public method whose name (or all
    of its underscore-separated tokens) appears nowhere in the summary counts as
    omitted; a class with two or more omitted public methods is reported so the
    summary is widened to name the broader surface. Classes with a multi-line
    docstring body are left to the audit lane, since their prose can carry the
    enumeration without naming each method by name.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per class whose single-line docstring omits two or more of its
        public methods, capped at the module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, ast.ClassDef):
            continue
        class_docstring = ast.get_docstring(each_node) or ""
        if not _class_docstring_summary_is_single_line(class_docstring):
            continue
        public_names = _public_method_names(each_node)
        if len(public_names) < MINIMUM_PUBLIC_METHODS_FOR_CLASS_DOCSTRING_BREADTH:
            continue
        unmentioned_names = _unmentioned_public_methods(each_node, class_docstring)
        if len(unmentioned_names) < MINIMUM_PUBLIC_METHODS_FOR_CLASS_DOCSTRING_BREADTH:
            continue
        issues.append(
            f"Line {each_node.lineno}: {each_node.name} one-line docstring omits "
            f"public method(s) {', '.join(unmentioned_names)} — widen the summary "
            "so it names the class's full public surface"
        )
        if len(issues) >= MAX_CLASS_DOCSTRING_PUBLIC_METHOD_ISSUES:
            break
    return issues[:MAX_CLASS_DOCSTRING_PUBLIC_METHOD_ISSUES]


def _docstring_claims_no_consumer(docstring_text: str) -> str:
    lowered_docstring = docstring_text.lower()
    for each_phrase in ALL_DOCSTRING_NO_CONSUMER_CLAIM_PHRASES:
        if each_phrase in lowered_docstring:
            return each_phrase
    return ""


def check_docstring_no_consumer_claim(content: str, file_path: str) -> list[str]:
    """Flag a docstring that asserts no consumer reads its produced artifact yet.

    A producer docstring claiming "no consumer reads it yet" (or
    "producer-only artifact") is a transitional statement that drifts the moment
    a consumer lands. Once a submission run, gate, or any reader loads the
    artifact, the claim contradicts both the live behavior and any companion
    SKILL.md that documents the consumer — the Category O8 docstring /
    companion-doc producer-consumer drift. The claim is also a no-historical /
    no-transitional-language violation in its own right: a docstring describes
    the contract that exists, not a not-yet-wired future. Rephrase to state what
    reads the artifact, or drop the no-consumer sentence entirely.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per function whose docstring claims no consumer reads its
        output, capped at the module limit.
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
        matched_phrase = _docstring_claims_no_consumer(docstring_text)
        if not matched_phrase:
            continue
        issues.append(
            f"Line {each_node.lineno}: {each_node.name}() docstring claims "
            f"'{matched_phrase}' — a no-consumer-yet claim drifts the moment a reader "
            "lands and contradicts any companion SKILL.md; state what reads the artifact "
            "or drop the sentence (Category O8 docstring / companion-doc drift)"
        )
        if len(issues) >= MAX_DOCSTRING_NO_CONSUMER_CLAIM_ISSUES:
            break
    return issues[:MAX_DOCSTRING_NO_CONSUMER_CLAIM_ISSUES]


def _module_docstring_summary_is_single_paragraph(module_docstring: str) -> bool:
    stripped_text = module_docstring.strip()
    if not stripped_text:
        return False
    return "\n" not in stripped_text


def _module_public_check_names(parsed_tree: ast.Module) -> list[str]:
    deduplicated_names: dict[str, None] = {}
    for each_statement in parsed_tree.body:
        if not isinstance(each_statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_statement.name.startswith("check_"):
            continue
        if _function_is_private_or_dunder(each_statement.name):
            continue
        deduplicated_names[each_statement.name] = None
    return list(deduplicated_names)


def _distinctive_name_tokens(check_name: str) -> list[str]:
    return [
        each_token
        for each_token in _name_tokens(check_name)
        if each_token.lower() not in ALL_GENERIC_CHECK_NAME_TOKENS
    ]


def _docstring_mentions_check(docstring_text: str, check_name: str) -> bool:
    lowered_docstring = docstring_text.lower()
    if check_name.lower() in lowered_docstring:
        return True
    distinctive_tokens = _distinctive_name_tokens(check_name)
    if not distinctive_tokens:
        return True
    return any(each_token.lower() in lowered_docstring for each_token in distinctive_tokens)


def check_module_docstring_names_public_checks(content: str, file_path: str) -> list[str]:
    """Flag a one-line module docstring that omits a public ``check_*`` function.

    A check-registry module whose docstring is a single summary paragraph names
    each check it dispatches, so a reader trusts that one line to be the full
    roster. When the module grows a public ``check_*`` entry point the summary
    never names, the enumeration under-describes the module — the
    docstring-prose-vs-implementation drift the repo flags as Category O6/O8.
    A check counts as named when the full ``check_*`` name, or any distinctive
    (non-generic) underscore-separated token of it, appears in the summary;
    generic tokens (``check``, ``test``, ``tests``) do not count. A module with
    two or more public checks and any check the summary never names is reported
    so the summary names the full roster. Modules with a multi-paragraph
    docstring body are left to the audit lane, since their prose can carry the
    roster without naming each check by name. This check covers hook
    infrastructure, where the affected check registries live.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per public check the single-paragraph module docstring omits,
        capped at the module limit.
    """
    if is_strict_test_file(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    module_docstring = ast.get_docstring(parsed_tree) or ""
    if not _module_docstring_summary_is_single_paragraph(module_docstring):
        return []
    public_check_names = _module_public_check_names(parsed_tree)
    if len(public_check_names) < MINIMUM_PUBLIC_CHECKS_FOR_MODULE_DOCSTRING_ROSTER:
        return []
    issues: list[str] = []
    for each_name in public_check_names:
        if _docstring_mentions_check(module_docstring, each_name):
            continue
        issues.append(
            f"Line 1: module docstring omits public check {each_name}() — name every "
            "public check_* function the module exposes so the roster is complete "
            "(Category O6/O8 docstring-vs-implementation drift)"
        )
        if len(issues) >= MAX_MODULE_DOCSTRING_CHECK_ROSTER_ISSUES:
            break
    return issues[:MAX_MODULE_DOCSTRING_CHECK_ROSTER_ISSUES]


def _module_string_tuple_members(parsed_tree: ast.Module) -> dict[str, frozenset[str]]:
    members_by_constant: dict[str, frozenset[str]] = {}
    for each_statement in parsed_tree.body:
        if not isinstance(each_statement, ast.Assign):
            continue
        if not isinstance(each_statement.value, ast.Tuple):
            continue
        literal_members: set[str] = set()
        every_member_is_identifier_shaped = True
        for each_element in each_statement.value.elts:
            if (
                isinstance(each_element, ast.Constant)
                and isinstance(each_element.value, str)
                and IDENTIFIER_SHAPED_TUPLE_MEMBER_PATTERN.match(each_element.value)
            ):
                literal_members.add(each_element.value.lstrip("."))
                continue
            every_member_is_identifier_shaped = False
            break
        if not every_member_is_identifier_shaped:
            continue
        if len(literal_members) < MINIMUM_TUPLE_MEMBERS_FOR_DOCSTRING_ENUMERATION:
            continue
        for each_target in each_statement.targets:
            if isinstance(each_target, ast.Name):
                members_by_constant[each_target.id] = frozenset(literal_members)
    return members_by_constant


def _names_referenced_in_function(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    return {
        each_node.id
        for each_node in ast.walk(function_node)
        if isinstance(each_node, ast.Name)
    }


def _docstring_inline_code_tokens(docstring_text: str) -> set[str]:
    tokens: set[str] = set()
    for each_match in INLINE_CODE_TOKEN_PATTERN.finditer(docstring_text):
        token = each_match.group(1).strip().lstrip(".")
        if token:
            tokens.add(token)
    return tokens


def check_docstring_tuple_enumeration_match(content: str, file_path: str) -> list[str]:
    """Flag a docstring enumeration that drifts from a literal tuple it reads.

    The drift this catches: a function reads a module-level tuple of literal
    string members and its docstring enumerates inline-code tokens that name
    some of those members, but the enumerated set and the tuple membership
    differ. A token the docstring lists that the tuple lacks, or a tuple member
    the docstring omits, misleads a reader who trusts the prose enumeration to
    match the detection set — the deterministic slice of Category O6
    docstring-prose-vs-implementation drift. The check binds only when the
    docstring's inline-code tokens overlap the tuple membership, so a docstring
    that names unrelated attributes is left alone. This check covers hook
    infrastructure, where the affected detection tuples live.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per function whose docstring enumeration diverges from the
        tuple it reads, capped at the module limit.
    """
    if is_strict_test_file(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    members_by_constant = _module_string_tuple_members(parsed_tree)
    if not members_by_constant:
        return []
    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        docstring_text = _function_docstring_text(each_node)
        if not docstring_text:
            continue
        docstring_tokens = _docstring_inline_code_tokens(docstring_text)
        if not docstring_tokens:
            continue
        referenced_names = _names_referenced_in_function(each_node)
        for each_constant_name in referenced_names & set(members_by_constant):
            tuple_members = members_by_constant[each_constant_name]
            if not (docstring_tokens & tuple_members):
                continue
            if docstring_tokens == tuple_members:
                continue
            docstring_only = sorted(docstring_tokens - tuple_members)
            tuple_only = sorted(tuple_members - docstring_tokens)
            issues.append(
                f"Line {each_node.lineno}: {each_node.name}() docstring enumerates "
                f"{sorted(docstring_tokens)} but {each_constant_name} holds "
                f"{sorted(tuple_members)} — docstring-only: {docstring_only}, "
                f"tuple-only: {tuple_only}; match the enumeration to the tuple "
                "(Category O6 docstring-vs-implementation drift)"
            )
            if len(issues) >= MAX_DOCSTRING_TUPLE_ENUMERATION_ISSUES:
                return issues[:MAX_DOCSTRING_TUPLE_ENUMERATION_ISSUES]
    return issues[:MAX_DOCSTRING_TUPLE_ENUMERATION_ISSUES]
