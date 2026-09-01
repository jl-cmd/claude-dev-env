"""Google-style docstring presence and docstring Args-versus-signature checks."""

import ast
import re
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_shared import (  # noqa: E402
    _scope_violations_to_changed_lines,
    _statement_is_docstring,
    _walk_skipping_nested_functions,
    _walk_skipping_type_checking_blocks,
    is_hook_infrastructure,
    is_strict_test_file,
    is_test_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_DATA_SCHEMA_CONSTANT_NAME_MARKERS,
    ALL_DATA_SCHEMA_DOCSTRING_ACKNOWLEDGEMENT_PHRASES,
    ALL_DOCSTRING_EXEMPT_DECORATOR_NAMES,
    ALL_DOCSTRING_FILE_REFERENCE_SUFFIXES,
    ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES,
    ALL_DOCSTRING_NON_CONSTANT_REFERENCE_MARKERS,
    ALL_DOCSTRING_RUNON_JOINER_MARKERS,
    ALL_GENERIC_CHECK_NAME_TOKENS,
    ALL_NAMING_CONVENTION_DESCRIPTOR_TOKENS,
    ALL_USER_FACING_TEXT_SCOPE_DOCSTRING_PHRASES,
    DOCSTRING_NARRATIVE_LINE_JOIN_SEPARATOR,
    DOCSTRING_NARRATIVE_PROSE_LINE_LIMIT,
    DOCSTRING_REFERENCE_MARKER_WINDOW,
    DOCSTRING_RUNON_SENTENCE_BOUNDARY_PATTERN,
    DOCSTRING_RUNON_SENTENCE_WORD_LIMIT,
    DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT,
    MAX_CLASS_DOCSTRING_PUBLIC_METHOD_ISSUES,
    MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES,
    MAX_DOCSTRING_FORMAT_ISSUES,
    MAX_DOCSTRING_PROSE_WALL_ISSUES,
    MAX_DOCSTRING_RUNON_SENTENCE_ISSUES,
    MAX_DOCSTRING_UNDEFINED_CONSTANT_ISSUES,
    MAX_MODULE_DOCSTRING_CHECK_ROSTER_ISSUES,
    MAX_MODULE_DOCSTRING_DATA_SCHEMA_SCOPE_ISSUES,
    MINIMUM_PUBLIC_CHECKS_FOR_MODULE_DOCSTRING_ROSTER,
    MINIMUM_PUBLIC_METHODS_FOR_CLASS_DOCSTRING_BREADTH,
    MINIMUM_SIBLING_OCCURRENCES_FOR_SHARED_TOKEN,
    MODULE_DOCSTRING_DATA_SCHEMA_CONSTANT_SAMPLE_LIMIT,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_CAPS_WITH_UNDERSCORE_PATTERN,
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


def check_docstring_documents_unreferenced_parameter(
    content: str, file_path: str
) -> list[str]:
    """Flag a documented Args parameter the function body never references.

    A parameter that appears in the ``Args:`` block but is named nowhere in the
    body is dead: the function does not read it, yet the docstring describes
    behavior keyed to it. The common shape is a flag that a caller wired in,
    then moved the real logic up a level — the parameter and its Args line stay
    behind, claiming a behavior the body does not implement. Both the unused
    parameter and the stale Args claim drift together, so the gate catches them
    as one finding.

    Functions whose signature accepts ``**kwargs`` are skipped, because a
    documented name may be a keyword key consumed through the kwargs mapping
    rather than a named parameter. Private, dunder, abstract, and stub-bodied
    functions are skipped, since a parameter declared for interface conformance
    legitimately goes unread.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per documented-but-unreferenced parameter, capped at the
        module limit.
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
        referenced_names = _names_referenced_in_function(each_node)
        for each_documented_name in documented_names:
            if each_documented_name not in real_names:
                continue
            if each_documented_name in referenced_names:
                continue
            issues.append(
                f"Line {each_node.lineno}: {each_node.name}() docstring Args: documents "
                f"'{each_documented_name}' but the body never references it - drop the "
                "unused parameter and its Args line, or use it"
            )
            if len(issues) >= MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES:
                return issues[:MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES]
    return issues[:MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES]


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


def _shared_sibling_name_tokens(all_check_names: list[str]) -> frozenset[str]:
    token_occurrence_count: dict[str, int] = {}
    for each_check_name in all_check_names:
        for each_token in set(each_token.lower() for each_token in _name_tokens(each_check_name)):
            token_occurrence_count[each_token] = token_occurrence_count.get(each_token, 0) + 1
    return frozenset(
        each_token
        for each_token, each_count in token_occurrence_count.items()
        if each_count >= MINIMUM_SIBLING_OCCURRENCES_FOR_SHARED_TOKEN
    )


def _module_distinctive_name_tokens(
    check_name: str, all_shared_sibling_tokens: frozenset[str]
) -> list[str]:
    return [
        each_token
        for each_token in _distinctive_name_tokens(check_name)
        if each_token.lower() not in all_shared_sibling_tokens
    ]


def _token_present_in_text(token: str, lowered_text: str) -> bool:
    lowered_token = token.lower()
    if lowered_token in lowered_text:
        return True
    return lowered_token.endswith("s") and lowered_token[:-1] in lowered_text


def _docstring_mentions_check(
    docstring_text: str, check_name: str, all_shared_sibling_tokens: frozenset[str]
) -> bool:
    lowered_docstring = docstring_text.lower()
    if check_name.lower() in lowered_docstring:
        return True
    distinguishing_tokens = _module_distinctive_name_tokens(check_name, all_shared_sibling_tokens)
    if not distinguishing_tokens:
        return True
    return any(
        _token_present_in_text(each_token, lowered_docstring)
        for each_token in distinguishing_tokens
    )


def check_module_docstring_names_public_checks(content: str, file_path: str) -> list[str]:
    """Flag a one-line module docstring that omits a public ``check_*`` function.

    A check-registry module whose docstring is a single summary paragraph names
    each check it dispatches, so a reader trusts that one line to be the full
    roster. When the module grows a public ``check_*`` entry point the summary
    never names, the enumeration under-describes the module — the
    docstring-prose-vs-implementation drift the repo flags as Category O6/O8.
    A check counts as named when the full ``check_*`` name, or a
    module-distinctive underscore-separated token of it, appears in the summary
    (matched allowing a trailing-``s`` plural). A token is module-distinctive
    when it is non-generic (generic tokens ``check``, ``test``, ``tests`` never
    count) and it is not shared by two or more of the module's check names — a
    token such as ``string`` or ``magic`` that recurs across sibling checks is
    no evidence that any one check is named, so a check whose only
    summary-present tokens are shared ones is reported. A check with no
    module-distinctive token is treated as named, since the summary cannot single
    it out. A module with two or more public checks and any check the summary
    never names is reported
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
    all_shared_sibling_tokens = _shared_sibling_name_tokens(public_check_names)
    issues: list[str] = []
    for each_name in public_check_names:
        if _docstring_mentions_check(module_docstring, each_name, all_shared_sibling_tokens):
            continue
        issues.append(
            f"Line 1: module docstring omits public check {each_name}() — name every "
            "public check_* function the module exposes so the roster is complete "
            "(Category O6/O8 docstring-vs-implementation drift)"
        )
        if len(issues) >= MAX_MODULE_DOCSTRING_CHECK_ROSTER_ISSUES:
            break
    return issues[:MAX_MODULE_DOCSTRING_CHECK_ROSTER_ISSUES]


def _module_level_upper_snake_constant_names(parsed_tree: ast.Module) -> list[str]:
    constant_names: list[str] = []
    for each_statement in parsed_tree.body:
        target_nodes: list[ast.expr] = []
        if isinstance(each_statement, ast.Assign):
            target_nodes = list(each_statement.targets)
        elif isinstance(each_statement, ast.AnnAssign):
            target_nodes = [each_statement.target]
        for each_target in target_nodes:
            if (
                isinstance(each_target, ast.Name)
                and ALL_CAPS_WITH_UNDERSCORE_PATTERN.match(each_target.id)
            ):
                constant_names.append(each_target.id)
    return constant_names


def _constant_name_data_schema_marker(constant_name: str) -> str:
    for each_marker in ALL_DATA_SCHEMA_CONSTANT_NAME_MARKERS:
        if each_marker in constant_name:
            return each_marker
    return ""


def _module_data_schema_constant_names(parsed_tree: ast.Module) -> list[str]:
    return [
        each_name
        for each_name in _module_level_upper_snake_constant_names(parsed_tree)
        if _constant_name_data_schema_marker(each_name)
    ]


def _module_docstring_claims_user_facing_text_scope(module_docstring: str) -> bool:
    lowered_docstring = module_docstring.lower()
    return any(
        each_phrase in lowered_docstring
        for each_phrase in ALL_USER_FACING_TEXT_SCOPE_DOCSTRING_PHRASES
    )


def _module_docstring_acknowledges_data_schema_scope(module_docstring: str) -> bool:
    lowered_docstring = module_docstring.lower()
    return any(
        each_phrase in lowered_docstring
        for each_phrase in ALL_DATA_SCHEMA_DOCSTRING_ACKNOWLEDGEMENT_PHRASES
    )


def check_module_docstring_scope_omits_data_schema_constants(
    content: str, file_path: str
) -> list[str]:
    """Flag a user-facing-text module docstring that omits data-schema constants.

    A module whose one-line docstring scopes its contents to user-facing text
    claims a strings-only surface, and a reader trusts that line to map the whole
    module. The drift this catches is a summary such as "User-facing strings: CLI
    flag names, help text, and log messages". The body below it also defines
    serialization field keys, run-metadata schema keys, and runtime config. The
    summary then under-describes the module, the Category O module-responsibility
    drift the repo flags. A constant counts as a data-schema or runtime-config
    value when its name carries a ``_FIELD_``, ``_KEY_``, ``_SCHEMA_``,
    ``_ENCODING``, or ``_FORMAT_STRING`` marker. The check fires only when the
    docstring claims a user-facing-text scope and acknowledges no data-schema or
    runtime-config category. A docstring that already names "field keys", "schema",
    or "runtime config" passes, so broadening the summary clears the gate.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue naming the unacknowledged data-schema constants, capped at the
        module limit.
    """
    if is_test_file(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    module_docstring = ast.get_docstring(parsed_tree) or ""
    if not _module_docstring_claims_user_facing_text_scope(module_docstring):
        return []
    if _module_docstring_acknowledges_data_schema_scope(module_docstring):
        return []
    data_schema_constant_names = _module_data_schema_constant_names(parsed_tree)
    if not data_schema_constant_names:
        return []
    sampled_names = ", ".join(
        data_schema_constant_names[:MODULE_DOCSTRING_DATA_SCHEMA_CONSTANT_SAMPLE_LIMIT]
    )
    return [
        "Line 1: module docstring scopes the module to user-facing text but the module "
        f"defines data-schema or runtime-config constants ({sampled_names}) the summary "
        "never names — broaden the summary to name the data-schema keys and "
        "runtime-config constants it holds (Category O module-responsibility drift)"
    ][:MAX_MODULE_DOCSTRING_DATA_SCHEMA_SCOPE_ISSUES]


def _names_referenced_in_function(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    return {
        each_node.id
        for each_node in ast.walk(function_node)
        if isinstance(each_node, ast.Name)
    }


def _imported_binding_names(import_node: ast.Import | ast.ImportFrom) -> set[str]:
    bound_names: set[str] = set()
    for each_alias in import_node.names:
        bound_names.add(each_alias.asname or each_alias.name.split(".", 1)[0])
    return bound_names


def _module_defined_and_imported_names(parsed_tree: ast.Module) -> set[str]:
    defined_names: set[str] = set()
    for each_node in ast.walk(parsed_tree):
        if isinstance(each_node, (ast.Import, ast.ImportFrom)):
            defined_names |= _imported_binding_names(each_node)
        elif isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined_names.add(each_node.name)
        elif isinstance(each_node, ast.Name) and isinstance(each_node.ctx, ast.Store):
            defined_names.add(each_node.id)
    return defined_names


def _module_attribute_access_names(parsed_tree: ast.Module) -> set[str]:
    attribute_names: set[str] = set()
    for each_node in ast.walk(parsed_tree):
        if isinstance(each_node, ast.Attribute):
            attribute_names.add(each_node.attr)
    return attribute_names


def _docstring_constant_node_ids(parsed_tree: ast.Module) -> set[int]:
    docstring_node_ids: set[int] = set()
    for each_node in ast.walk(parsed_tree):
        if not isinstance(
            each_node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body_statements = each_node.body
        if not body_statements or not _statement_is_docstring(body_statements[0]):
            continue
        first_statement = body_statements[0]
        assert isinstance(first_statement, ast.Expr)
        docstring_node_ids.add(id(first_statement.value))
    return docstring_node_ids


def _module_string_literal_word_runs(parsed_tree: ast.Module) -> set[str]:
    docstring_node_ids = _docstring_constant_node_ids(parsed_tree)
    word_runs: set[str] = set()
    for each_node in ast.walk(parsed_tree):
        if not (isinstance(each_node, ast.Constant) and isinstance(each_node.value, str)):
            continue
        if id(each_node) in docstring_node_ids:
            continue
        for each_run in re.findall(r"[A-Za-z0-9_]+", each_node.value):
            if ALL_CAPS_WITH_UNDERSCORE_PATTERN.match(each_run):
                word_runs.add(each_run)
    return word_runs


def _name_word_prefix_families(all_supporting_names: set[str]) -> set[str]:
    prefix_families: set[str] = set()
    for each_name in all_supporting_names:
        leading_word = each_name.split("_", 1)[0]
        prefix_families.add(leading_word)
    return prefix_families


def _token_is_word_run_of_any_name(token: str, all_supporting_names: set[str]) -> bool:
    return any(f"_{token}_" in f"_{each_name}_" for each_name in all_supporting_names)


def _docstring_words(docstring_text: str) -> list[str]:
    return [
        each_word.strip(".,:;()[]{}'\"`")
        for each_word in docstring_text.replace("`", " ").split()
    ]


def _docstring_frames_token_as_non_constant_reference(
    token: str, docstring_text: str
) -> bool:
    if any(
        f"{token}{each_suffix}" in docstring_text
        for each_suffix in ALL_DOCSTRING_FILE_REFERENCE_SUFFIXES
    ):
        return True
    words = _docstring_words(docstring_text)
    for each_index, each_word in enumerate(words):
        if each_word != token:
            continue
        neighbors = words[max(each_index - DOCSTRING_REFERENCE_MARKER_WINDOW, 0) : each_index + DOCSTRING_REFERENCE_MARKER_WINDOW + 1]
        if any(
            each_neighbor.lower() in ALL_DOCSTRING_NON_CONSTANT_REFERENCE_MARKERS
            for each_neighbor in neighbors
        ):
            return True
    return False


def _docstring_constant_token_is_supported(
    token: str, parsed_tree: ast.Module, all_known_names: set[str], docstring_text: str
) -> bool:
    supporting_predicates = (
        lambda: token in all_known_names,
        lambda: token in ALL_NAMING_CONVENTION_DESCRIPTOR_TOKENS,
        lambda: token in _module_attribute_access_names(parsed_tree),
        lambda: token in _module_string_literal_word_runs(parsed_tree),
        lambda: _token_is_word_run_of_any_name(token, all_known_names),
        lambda: _docstring_frames_token_as_non_constant_reference(token, docstring_text),
        lambda: token.split("_", 1)[0] in _name_word_prefix_families(all_known_names),
    )
    return any(each_predicate() for each_predicate in supporting_predicates)


def _docstring_constant_tokens(docstring_text: str) -> set[str]:
    candidate_tokens: set[str] = set()
    for each_word in docstring_text.replace("`", " ").split():
        stripped_word = each_word.strip(".,:;()[]{}'\"")
        if stripped_word.startswith("__") and stripped_word.endswith("__"):
            continue
        if ALL_CAPS_WITH_UNDERSCORE_PATTERN.match(stripped_word):
            candidate_tokens.add(stripped_word)
    return candidate_tokens


def _documentable_nodes_with_docstrings(
    parsed_tree: ast.Module,
) -> list[tuple[int, str]]:
    documentable: list[tuple[int, str]] = []
    module_docstring = ast.get_docstring(parsed_tree)
    if module_docstring:
        documentable.append((1, module_docstring))
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(
            each_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        node_docstring = ast.get_docstring(each_node)
        if node_docstring:
            documentable.append((each_node.lineno, node_docstring))
    return documentable


def check_docstring_names_undefined_constant(content: str, file_path: str) -> list[str]:
    """Flag a docstring naming an UPPER_SNAKE constant nothing in the module backs.

    The drift this catches: a docstring names an all-caps, underscore-joined
    token as a contract identifier (``NATIVE_EVALUATE_FUNCTION_NAME``) while the
    enclosing module carries no supporting reference for it. A reader who trusts
    the docstring to name a real symbol finds nothing — the deterministic slice
    of Category O6 docstring-prose-vs-implementation drift where the named token
    is structurally a constant and unresolvable against the module.

    A token counts as supported, and is left alone, when any of these holds: it
    is defined at module scope or imported; it is a naming-convention descriptor
    (``UPPER_SNAKE_CASE`` and its siblings, describing a style, not a symbol); it
    is the attribute of an attribute access in the body (``os.O_NOFOLLOW``,
    ``config.timing.MAX_DELAY``, resolving stdlib and dotted-import constants);
    it is an all-caps word run inside a string literal (an env-var key read via
    ``os.environ[...]`` or ``os.getenv(...)``, an API enum string value, a doc
    stem in ``CODE_RULES.md``); it is a contiguous word run of a defined or
    imported name (``GH_TOKEN`` within ``ALL_GH_TOKEN_ENV_VAR_NAMES``); it shares
    a leading word component with a defined or imported name, marking the same
    enum family (``MODE_CLASSIFY`` beside an imported ``MODE_STRICT``); or the
    docstring prose frames it as a non-constant reference — followed by a file
    suffix (``CODE_RULES.md``) or sitting within two words of a marker such as
    ``rule``, ``doc``, ``file``, ``env``, ``variable``, ``set``, ``read``,
    ``per``, ``follows``, or ``see`` (``per CODE_RULES``, ``LLM_SETTINGS_ROOT is
    set to``). Single-segment all-caps acronyms (``HTTP``, ``JSON``) and dunder
    names (``__all__``) are not constants and are left alone.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per docstring token that no module reference backs, capped at
        the module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    known_names = _module_defined_and_imported_names(parsed_tree)
    issues: list[str] = []
    for each_line_number, each_docstring in _documentable_nodes_with_docstrings(parsed_tree):
        for each_token in sorted(_docstring_constant_tokens(each_docstring)):
            if _docstring_constant_token_is_supported(
                each_token, parsed_tree, known_names, each_docstring
            ):
                continue
            issues.append(
                f"Line {each_line_number}: docstring names '{each_token}' which the "
                "module neither defines at module scope nor imports — name the real "
                "symbol or drop the reference (Category O6 docstring-vs-implementation "
                "drift)"
            )
            if len(issues) >= MAX_DOCSTRING_UNDEFINED_CONSTANT_ISSUES:
                return issues[:MAX_DOCSTRING_UNDEFINED_CONSTANT_ISSUES]
    return issues[:MAX_DOCSTRING_UNDEFINED_CONSTANT_ISSUES]


def _is_narrative_cut_header(stripped_line: str) -> bool:
    return (
        stripped_line in ALL_DOCSTRING_TERMINATING_SECTION_HEADERS
        or stripped_line in ALL_DOCSTRING_ARGS_SECTION_HEADERS
    )


def _docstring_narrative_partition(docstring_text: str) -> tuple[list[str], bool]:
    """Split a docstring narrative into its prose lines and whether it shows an example.

    Walk the narrative up to the first ``Args:``/``Returns:`` cut header and sort
    every line into one of two buckets::

        Render the report so the reader sees how it ended.   <- prose line
        A finished run versus an interrupted one::           <- prose line (opener)
            theme_42 -- interrupted -> marked in-flight       -- indented example body
            OK:   a clean run reads differently in the log    -- indented example body
        The reader reads the final outcome at a glance.      <- prose line

    A ``>>>`` doctest region and a ``::`` block with an indented body both count as
    an illustration, so their lines never join the prose bucket. The caller reads
    the prose count to size the wall and the flag to know whether an example is present.
    """
    prose_lines: list[str] = []
    has_illustration = False
    all_lines = docstring_text.splitlines()
    total_lines = len(all_lines)
    line_index = 0
    while line_index < total_lines:
        raw_line = all_lines[line_index]
        stripped_line = raw_line.strip()
        if _is_narrative_cut_header(stripped_line):
            break
        if stripped_line.startswith(">>>"):
            has_illustration = True
            line_index += 1
            while line_index < total_lines:
                inner_stripped = all_lines[line_index].strip()
                if not inner_stripped or _is_narrative_cut_header(inner_stripped):
                    break
                line_index += 1
            continue
        if stripped_line.endswith("::"):
            opener_indent = len(raw_line) - len(raw_line.lstrip())
            probe_index = line_index + 1
            has_indented_body = False
            while probe_index < total_lines:
                probe_raw = all_lines[probe_index]
                probe_stripped = probe_raw.strip()
                if not probe_stripped:
                    probe_index += 1
                    continue
                probe_indent = len(probe_raw) - len(probe_raw.lstrip())
                if probe_indent > opener_indent:
                    has_indented_body = True
                    probe_index += 1
                    continue
                break
            if has_indented_body:
                has_illustration = True
                prose_lines.append(stripped_line)
                line_index = probe_index
                continue
        if stripped_line:
            prose_lines.append(stripped_line)
        line_index += 1
    return prose_lines, has_illustration


def _docstring_narrative_text(docstring_text: str) -> str:
    prose_lines, _has_illustration = _docstring_narrative_partition(docstring_text)
    return DOCSTRING_NARRATIVE_LINE_JOIN_SEPARATOR.join(prose_lines)


def _sentence_word_count(sentence_text: str) -> int:
    return sum(
        1
        for each_token in sentence_text.split()
        if any(each_character.isalnum() for each_character in each_token)
    )


def _sentence_carries_joiner_marker(sentence_text: str) -> bool:
    return any(
        each_marker in sentence_text for each_marker in ALL_DOCSTRING_RUNON_JOINER_MARKERS
    )


def _runon_sentences(narrative_text: str) -> list[str]:
    flagged_sentences: list[str] = []
    for each_sentence in DOCSTRING_RUNON_SENTENCE_BOUNDARY_PATTERN.split(narrative_text):
        stripped_sentence = each_sentence.strip()
        if not stripped_sentence:
            continue
        if _sentence_word_count(stripped_sentence) <= DOCSTRING_RUNON_SENTENCE_WORD_LIMIT:
            continue
        if not _sentence_carries_joiner_marker(stripped_sentence):
            continue
        flagged_sentences.append(stripped_sentence)
    return flagged_sentences


def _docstring_owner_span(owner_node: ast.AST, anchor_lineno: int) -> range:
    """Lines from the owner's anchor through the end of its docstring statement.

    ::

        def clean_helper() -> str:              <- anchor (def / class line)
            '''run-on narrative across lines''' <- docstring end
            return "ok"                         <- outside the span

        An edit that only rewrites the docstring body intersects this span and
        re-grades the finding. An edit to the return line does not.
    """
    body = getattr(owner_node, "body", None) or []
    if not body:
        return range(anchor_lineno, anchor_lineno + 1)
    first_statement = body[0]
    end_lineno = getattr(first_statement, "end_lineno", None) or first_statement.lineno
    return range(anchor_lineno, end_lineno + 1)


def _documentable_docstring_targets(
    parsed_tree: ast.Module,
) -> list[tuple[int, str, str, range]]:
    documentable_targets: list[tuple[int, str, str, range]] = []
    module_docstring = ast.get_docstring(parsed_tree)
    if module_docstring and parsed_tree.body:
        module_anchor = parsed_tree.body[0].lineno
        documentable_targets.append(
            (
                module_anchor,
                "module",
                module_docstring,
                _docstring_owner_span(parsed_tree, module_anchor),
            )
        )
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if isinstance(each_node, ast.ClassDef):
            class_docstring = ast.get_docstring(each_node)
            if class_docstring:
                documentable_targets.append(
                    (
                        each_node.lineno,
                        each_node.name,
                        class_docstring,
                        _docstring_owner_span(each_node, each_node.lineno),
                    )
                )
            continue
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_private_or_dunder(each_node.name):
            continue
        if _function_has_exempt_decorator(each_node):
            continue
        function_docstring = _function_docstring_text(each_node)
        if function_docstring:
            documentable_targets.append(
                (
                    each_node.lineno,
                    f"{each_node.name}()",
                    function_docstring,
                    _docstring_owner_span(each_node, each_node.lineno),
                )
            )
    return documentable_targets


def check_docstring_runon_sentence(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag a docstring narrative sentence that reads as a dense run-on wall.

    A readable docstring breaks its narrative into short sentences a general
    developer follows on the first read. The one mechanical mark of a wall is a
    single sentence that runs past the word limit while chaining clauses with an
    em-dash, a double-hyphen, or a semicolon. This check inspects the narrative prose of module,
    class, and public-function docstrings - the text before the first structured
    section header (``Args:``, ``Arguments:``, ``Returns:``, ``Yields:``,
    ``Raises:``, ``Note:``, ``Notes:``, ``Example:``, or ``Examples:``) - and
    reports a sentence that is both over the word limit and joined by one of those
    marks.
    Whether the prose paints a concrete, illustrative picture is judgment the
    plain-illustrative-docstrings audit lane carries; this gate catches only the
    run-on mark.

    The caller passes the reconstructed full file as *content* so ``ast.parse``
    sees a complete module. Findings are then scoped to *all_changed_lines* so an
    Edit blocks on a run-on it just introduced while a pre-existing far-away
    run-on on an untouched definition does not block the edit.

    Args:
        content: The source text to inspect - the reconstructed full file on an
            Edit so the parse succeeds.
        file_path: The path the source will be written to, used for exemptions.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a finding
            blocks only when its definition-through-docstring span intersects
            the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line.

    Returns:
        One issue per docstring whose narrative carries a run-on sentence, capped
        at the module limit and scoped to the changed lines unless
        *defer_scope_to_caller* is True or *all_changed_lines* is None.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for (
        each_line_number,
        each_label,
        each_docstring,
        each_span,
    ) in _documentable_docstring_targets(parsed_tree):
        flagged_sentences = _runon_sentences(_docstring_narrative_text(each_docstring))
        if not flagged_sentences:
            continue
        run_on_word_count = _sentence_word_count(flagged_sentences[0])
        message = (
            f"Line {each_line_number}: {each_label} docstring carries a {run_on_word_count}-word "
            "run-on sentence - break the narrative into short, illustrative sentences a general "
            "developer reads in one pass (plain-illustrative-docstrings)"
        )
        all_violations_in_walk_order.append((each_span, message))
    scoped_issues = _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
    return scoped_issues[:MAX_DOCSTRING_RUNON_SENTENCE_ISSUES]


def check_docstring_prose_wall_without_illustration(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag a summary that tells for many sentences and shows nothing.

    A reader trusts the opening to paint a scene. A run of short sentences with
    no worked example leaves the reader piecing that scene together alone::

        A calm voyage ends well for every vessel.            <- one more line
        A halted voyage marks the vessel it neared.          <- and another
        ... more like these, no worked example ...           flag: a wall, no scene
        A calm voyage versus a halted one::                  ok: a worked example
            a lone vessel -- halted -> marked mid-voyage

    Past the prose-line limit with no ``::`` listing and no ``>>>`` doctest, this
    fires. A narrative that shows a worked example, or one at the limit, passes.

    The caller passes the reconstructed full file as *content* so ``ast.parse``
    sees a complete module. Findings are then scoped to *all_changed_lines* so an
    Edit blocks on a wall it just introduced while a pre-existing far-away wall
    on an untouched definition does not block the edit.

    Args:
        content: The source text to inspect - the reconstructed full file on an
            Edit so the parse succeeds.
        file_path: The path the source will be written to, used for exemptions.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a finding
            blocks only when its definition-through-docstring span intersects
            the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line.

    Returns:
        One issue per summary that runs a wall of sentences with no worked
        example, capped at the issue limit for the rule and scoped to the
        changed lines unless *defer_scope_to_caller* is True or
        *all_changed_lines* is None.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for (
        each_line_number,
        each_label,
        each_docstring,
        each_span,
    ) in _documentable_docstring_targets(parsed_tree):
        prose_lines, has_illustration = _docstring_narrative_partition(each_docstring)
        if has_illustration:
            continue
        prose_line_count = len(prose_lines)
        if prose_line_count <= DOCSTRING_NARRATIVE_PROSE_LINE_LIMIT:
            continue
        message = (
            f"Line {each_line_number}: {each_label} summary runs {prose_line_count} "
            "narrative lines with no worked example - show, don't tell: swap the wall for a "
            "'::' listing (a sample input, an annotated outcome, ok/flag contrast rows) and "
            "keep the narrative to a few short lines (plain-illustrative-docstrings)"
        )
        all_violations_in_walk_order.append((each_span, message))
    scoped_issues = _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
    return scoped_issues[:MAX_DOCSTRING_PROSE_WALL_ISSUES]


