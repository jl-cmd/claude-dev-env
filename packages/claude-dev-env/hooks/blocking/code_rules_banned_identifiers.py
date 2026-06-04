"""Banned identifier, banned noun-word, and banned function-prefix naming checks."""

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
    _collect_annotated_arguments,
    _collect_target_names,
    _scope_violations_to_changed_lines,
    _walk_skipping_type_checking_blocks,
    is_hook_infrastructure,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.banned_identifiers_constants import (  # noqa: E402
    ALL_BANNED_IDENTIFIERS,
    ALL_BANNED_NOUN_WORDS,
    BANNED_IDENTIFIER_MESSAGE_SUFFIX,
    BANNED_IDENTIFIER_SKIP_ADVISORY,
    BANNED_NOUN_WORD_MESSAGE_SUFFIX,
    CAMEL_CASE_WORD_PATTERN,
    MAX_BANNED_IDENTIFIER_ISSUES,
)
from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_BANNED_PREFIX_NAMES,
    MAX_BANNED_PREFIX_ISSUES,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_SELF_AND_CLS_PARAMETER_NAMES,
    BANNED_NOUN_SPAN_FRAGMENT_TEMPLATE,
)


def _collect_banned_names_from_target(target: ast.expr) -> list[ast.Name]:
    """Return every banned ast.Name reachable through tuple/list unpacking or starred targets."""
    return [
        each_name_node
        for each_name_node in _collect_target_names(target)
        if each_name_node.id in ALL_BANNED_IDENTIFIERS
    ]


def _value_is_parse_args_namespace_call(value_node: ast.AST | None) -> bool:
    if value_node is None:
        return False
    if not isinstance(value_node, ast.Call):
        return False
    callee = value_node.func
    return isinstance(callee, ast.Attribute) and callee.attr == "parse_args"


def _without_parse_args_namespace_exemption(
    all_banned_names: list[ast.Name], value_node: ast.AST | None
) -> list[ast.Name]:
    if not _value_is_parse_args_namespace_call(value_node):
        return all_banned_names
    return [each_name for each_name in all_banned_names if each_name.id != "args"]


def _synthesize_alias_name_node(
    bound_identifier: str, alias_node: ast.alias
) -> ast.Name:
    synthetic_name = ast.Name(id=bound_identifier, ctx=ast.Store())
    synthetic_name.lineno = alias_node.lineno
    synthetic_name.col_offset = alias_node.col_offset
    return synthetic_name


def _collect_banned_names_from_import(
    import_statement: ast.Import | ast.ImportFrom,
) -> list[ast.Name]:
    banned_alias_nodes: list[ast.Name] = []
    for each_alias in import_statement.names:
        bound_identifier = each_alias.asname or each_alias.name.split(".")[0]
        if bound_identifier in ALL_BANNED_IDENTIFIERS:
            banned_alias_nodes.append(
                _synthesize_alias_name_node(bound_identifier, each_alias)
            )
    return banned_alias_nodes


def _collect_banned_names_from_node(node: ast.AST) -> list[ast.Name]:
    """Return banned ast.Name nodes introduced by a single binding construct."""
    if isinstance(node, ast.Assign):
        banned_names: list[ast.Name] = []
        for each_target in node.targets:
            banned_names.extend(_collect_banned_names_from_target(each_target))
        return _without_parse_args_namespace_exemption(banned_names, node.value)
    if isinstance(node, ast.AnnAssign):
        banned_names = _collect_banned_names_from_target(node.target)
        return _without_parse_args_namespace_exemption(banned_names, node.value)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return _collect_banned_names_from_target(node.target)
    if isinstance(node, ast.comprehension):
        return _collect_banned_names_from_target(node.target)
    if isinstance(node, ast.withitem):
        if node.optional_vars is None:
            return []
        return _collect_banned_names_from_target(node.optional_vars)
    if isinstance(node, ast.NamedExpr):
        banned_names = _collect_banned_names_from_target(node.target)
        return _without_parse_args_namespace_exemption(banned_names, node.value)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return _collect_banned_names_from_import(node)
    return []


def check_banned_identifiers(content: str, file_path: str) -> list[str]:
    """Flag assignments to identifiers banned by the project Naming rules."""
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        print(f"{file_path}: {BANNED_IDENTIFIER_SKIP_ADVISORY}", file=sys.stderr)
        return []

    banned_name_nodes: list[ast.Name] = []
    for each_node in ast.walk(parsed_tree):
        banned_name_nodes.extend(_collect_banned_names_from_node(each_node))

    banned_name_nodes.sort(key=lambda each_name: (each_name.lineno, each_name.col_offset))

    issues: list[str] = []
    for each_name in banned_name_nodes:
        issues.append(
            f"Line {each_name.lineno}: Banned identifier '{each_name.id}' - {BANNED_IDENTIFIER_MESSAGE_SUFFIX}"
        )
        if len(issues) >= MAX_BANNED_IDENTIFIER_ISSUES:
            break

    return issues


def _identifier_word_parts(identifier: str) -> list[str]:
    """Split an identifier into lowercase word parts.

    Handles snake_case (split on ``_``), SCREAMING_SNAKE_CASE, and camelCase /
    PascalCase (split on capital-letter boundaries). Returns a list of
    lowercased word tokens for membership comparison against banned-noun
    vocabularies.

    Args:
        identifier: A Python identifier (variable, parameter, class, or
            function name).

    Returns:
        Word tokens in their original order, lowercased. Empty list when the
        identifier carries no letter characters.
    """
    all_words: list[str] = []
    for each_snake_segment in identifier.split("_"):
        if not each_snake_segment:
            continue
        camel_pieces = CAMEL_CASE_WORD_PATTERN.findall(each_snake_segment)
        if camel_pieces:
            for each_piece in camel_pieces:
                all_words.append(each_piece.lower())
        else:
            all_words.append(each_snake_segment.lower())
    return all_words


def _find_banned_noun_word(identifier: str) -> str | None:
    """Return the first banned-noun word embedded in *identifier*, or None.

    Args:
        identifier: A Python identifier.

    Returns:
        The lowercased banned noun word that appears as a word part inside the
        identifier (e.g., ``'result'`` for ``'HolidayPeakResult'``). Returns
        ``None`` when no banned noun word is present.
    """
    for each_word in _identifier_word_parts(identifier):
        if each_word in ALL_BANNED_NOUN_WORDS:
            return each_word
    return None


def _is_dunder_name(identifier: str) -> bool:
    return identifier.startswith("__") and identifier.endswith("__")


def _collect_banned_noun_word_bindings(
    parsed_tree: ast.AST,
) -> list[tuple[str, int, int, str]]:
    """Yield ``(identifier, lineno, col_offset, banned_word)`` for each binding.

    Walks assignment targets, annotated assignments, function/method
    parameters, function/method definitions, and class definitions. Skips
    identifiers that already match ``ALL_BANNED_IDENTIFIERS`` exactly (those
    are reported by ``check_banned_identifiers``) and dunder names.
    """
    flagged_bindings: list[tuple[str, int, int, str]] = []
    seen_keys: set[tuple[str, int, int]] = set()

    def record(name: str, lineno: int, col_offset: int) -> None:
        if name in ALL_BANNED_IDENTIFIERS:
            return
        if _is_dunder_name(name):
            return
        banned_word = _find_banned_noun_word(name)
        if banned_word is None:
            return
        key = (name, lineno, col_offset)
        if key in seen_keys:
            return
        seen_keys.add(key)
        flagged_bindings.append((name, lineno, col_offset, banned_word))

    for each_node in ast.walk(parsed_tree):
        if isinstance(each_node, ast.Assign):
            for each_target in each_node.targets:
                for each_name_node in _collect_target_names(each_target):
                    record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, ast.AnnAssign):
            for each_name_node in _collect_target_names(each_node.target):
                record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, (ast.For, ast.AsyncFor)):
            for each_name_node in _collect_target_names(each_node.target):
                record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, ast.NamedExpr) and isinstance(each_node.target, ast.Name):
            record(each_node.target.id, each_node.target.lineno, each_node.target.col_offset)
        elif isinstance(each_node, ast.comprehension):
            for each_name_node in _collect_target_names(each_node.target):
                record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, ast.withitem) and each_node.optional_vars is not None:
            for each_name_node in _collect_target_names(each_node.optional_vars):
                record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            record(each_node.name, each_node.lineno, each_node.col_offset)
            for each_arg in _collect_annotated_arguments(each_node):
                if each_arg.arg in ALL_SELF_AND_CLS_PARAMETER_NAMES:
                    continue
                record(each_arg.arg, each_arg.lineno, each_arg.col_offset)
        elif isinstance(each_node, ast.ClassDef):
            record(each_node.name, each_node.lineno, each_node.col_offset)
        elif isinstance(each_node, (ast.Import, ast.ImportFrom)):
            for each_alias in each_node.names:
                if each_alias.asname is None:
                    continue
                record(each_alias.asname, each_node.lineno, each_node.col_offset)

    flagged_bindings.sort(key=lambda binding: (binding[1], binding[2]))
    return flagged_bindings


def check_banned_noun_word_boundary(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag identifiers containing CODE_RULES naming-rule banned noun words.

    Companion to ``check_banned_identifiers`` (exact-match cases only). This
    check catches the wider pattern: a banned noun word from
    ``ALL_BANNED_NOUN_WORDS`` — the singular nouns ``result``, ``data``,
    ``output``, ``response``, ``value``, ``item``, ``temp`` plus the plural
    forms ``results``, ``outputs``, ``responses``, ``values``, ``items`` —
    appearing as a snake_case word part or camelCase word part inside a longer
    identifier (``canned_results``, ``HolidayPeakResult``, ``OUTPUT_DIR``,
    ``cached_response``).

    Skips test files, config files, hook infrastructure, workflow registries,
    and migrations. Identifiers that exactly match ``ALL_BANNED_IDENTIFIERS``
    are skipped because they are already reported by
    ``check_banned_identifiers``.

    Scoping mirrors ``check_function_length`` and
    ``check_tests_use_isolated_filesystem_paths`` through the shared
    ``_scope_violations_to_changed_lines`` helper. A banned-noun binding is a
    point fact about one identifier, so its enclosing unit is its own binding
    line: each violation carries the binding line as a one-line ``range`` for
    terminal diff scoping and a ``(binding span at line X, spanning 1 lines)``
    message fragment the commit gate reconstructs through the same shared span
    extractor registry the other two scoped checks use. Anchoring to the
    binding line (rather than the whole enclosing function) matches the
    companion exact-match ``check_banned_identifiers`` and keeps a pre-existing
    binding out of scope when an unrelated line of its enclosing function is
    edited. On a terminal Edit only violations whose binding line is among
    ``all_changed_lines`` are returned; on a new-file or full-file write every
    violation is in scope; ``defer_scope_to_caller`` returns every violation so
    the gate scopes by added line.

    Args:
        content: The reconstructed effective file content to analyze (the
            whole post-edit file on an Edit, the whole file at the gate).
        file_path: The path of the file being checked (used for exemption
            routing).
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when its binding line is among the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line and report the in-scope set.

    Returns:
        Issue strings, each describing one offending binding. When
        *defer_scope_to_caller* is True every binding is returned for the gate
        to scope; otherwise every binding in scope is returned.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path):
        return []
    if is_migration_file(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    single_line_span = 1
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_name, each_lineno, _, each_word in _collect_banned_noun_word_bindings(parsed_tree):
        span_range = range(each_lineno, each_lineno + single_line_span)
        span_fragment = BANNED_NOUN_SPAN_FRAGMENT_TEMPLATE.format(
            definition_line=each_lineno, line_span=single_line_span
        )
        message = (
            f"Line {each_lineno}: Identifier {each_name!r} {BANNED_NOUN_WORD_MESSAGE_SUFFIX} "
            f"(word: {each_word!r}) {span_fragment}"
        )
        all_violations_in_walk_order.append((span_range, message))
    return _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )


def check_banned_prefixes(content: str, file_path: str) -> list[str]:
    """Flag function and method names using generic banned prefixes.

    Per CODE_RULES.md / AGENTS.md Naming, function names use specific verbs.
    Generic prefixes ``handle_``, ``process_``, ``manage_``, ``do_`` are
    placeholders that hide the actual responsibility and are flagged so the
    author renames the function to a specific verb.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path) or is_config_file(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    flagged_function_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(each_node.name.startswith(each_prefix) for each_prefix in ALL_BANNED_PREFIX_NAMES):
            flagged_function_nodes.append(each_node)

    flagged_function_nodes.sort(key=lambda each_function: each_function.lineno)

    issues: list[str] = []
    for each_function in flagged_function_nodes:
        issues.append(
            f"Line {each_function.lineno}: Function '{each_function.name}' uses banned prefix - "
            "rename to a specific verb (see CODE_RULES Naming section)"
        )
        if len(issues) >= MAX_BANNED_PREFIX_ISSUES:
            break

    return issues
