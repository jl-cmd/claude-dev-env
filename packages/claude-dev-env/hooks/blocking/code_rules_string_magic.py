"""Bare string-literal magic, inline literal-collection, inline tuple string-magic, and whitespace-indentation magic checks."""

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

from code_rules_path_utils import (  # noqa: E402
    is_config_file,
)
from code_rules_shared import (  # noqa: E402
    _walk_skipping_nested_function_defs,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_CAPS_WITH_UNDERSCORE_PATTERN,
    DOTTED_SEGMENT_PATTERN,
    INDENTATION_MAGIC_MINIMUM_SPACE_RUN,
    INDENTATION_MAGIC_MINIMUM_TAB_RUN,
    INLINE_COLLECTION_MIN_LENGTH,
    MAX_WHITESPACE_INDENTATION_MAGIC_ISSUES,
    WHITESPACE_INDENTATION_MAGIC_MESSAGE_SUFFIX,
)
from hooks_constants.inline_tuple_string_magic_constants import (  # noqa: E402
    ALL_SNAKE_CASE_KEYWORD_EXEMPTIONS,
    EXPECTED_TUPLE_PAIR_LENGTH,
    INLINE_TUPLE_STRING_MAGIC_MESSAGE_SUFFIX,
    MAX_INLINE_TUPLE_STRING_MAGIC_ISSUES,
    SNAKE_CASE_LITERAL_PATTERN,
)


def _is_magic_string_literal(string_value: str) -> bool:
    if not string_value:
        return False
    if ALL_CAPS_WITH_UNDERSCORE_PATTERN.match(string_value):
        return True
    if DOTTED_SEGMENT_PATTERN.match(string_value):
        return True
    return False


def _collect_docstring_node_ids(tree: ast.Module) -> set[int]:
    docstring_ids: set[int] = set()
    docstring_owner_node_types = (
        ast.Module,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )
    for each_node in ast.walk(tree):
        if not isinstance(each_node, docstring_owner_node_types):
            continue
        if not each_node.body:
            continue
        first_statement = each_node.body[0]
        if not isinstance(first_statement, ast.Expr):
            continue
        first_value = first_statement.value
        if isinstance(first_value, ast.Constant) and isinstance(first_value.value, str):
            docstring_ids.add(id(first_value))
    return docstring_ids


def _collect_fstring_part_node_ids(tree: ast.Module) -> set[int]:
    fstring_part_ids: set[int] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.JoinedStr):
            continue
        for each_value in each_node.values:
            if isinstance(each_value, ast.Constant) and isinstance(each_value.value, str):
                fstring_part_ids.add(id(each_value))
    return fstring_part_ids


def check_string_literal_magic(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    docstring_node_ids = _collect_docstring_node_ids(tree)
    fstring_part_node_ids = _collect_fstring_part_node_ids(tree)
    issues: list[str] = []
    flagged_node_ids: set[int] = set()
    for each_function_node in ast.walk(tree):
        if not isinstance(each_function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_body_statement in each_function_node.body:
            for each_descendant in _walk_skipping_nested_function_defs(each_body_statement):
                if not isinstance(each_descendant, ast.Constant):
                    continue
                if not isinstance(each_descendant.value, str):
                    continue
                if id(each_descendant) in flagged_node_ids:
                    continue
                if id(each_descendant) in docstring_node_ids:
                    continue
                if id(each_descendant) in fstring_part_node_ids:
                    continue
                if not _is_magic_string_literal(each_descendant.value):
                    continue
                flagged_node_ids.add(id(each_descendant))
                issues.append(
                    f"Line {each_descendant.lineno}: string magic value {each_descendant.value!r}"
                    f" - extract to config/"
                )
    return issues


def check_inline_literal_collections(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    flagged_node_ids: set[int] = set()
    for each_function_node in ast.walk(tree):
        if not isinstance(each_function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_body_statement in each_function_node.body:
            for each_descendant in _walk_skipping_nested_function_defs(each_body_statement):
                if not isinstance(each_descendant, (ast.Set, ast.List)):
                    continue
                if id(each_descendant) in flagged_node_ids:
                    continue
                all_elements = each_descendant.elts
                if len(all_elements) < INLINE_COLLECTION_MIN_LENGTH:
                    continue
                if not all(isinstance(each_element, ast.Constant) for each_element in all_elements):
                    continue
                flagged_node_ids.add(id(each_descendant))
                collection_kind = "set" if isinstance(each_descendant, ast.Set) else "list"
                issues.append(
                    f"Line {each_descendant.lineno}: inline {collection_kind} literal of {len(all_elements)}"
                    f" constants in function body - extract to config/"
                )
    return issues


def check_inline_tuple_string_magic(content: str, file_path: str) -> list[str]:
    """Flag inline two-tuple literals whose first element is a snake_case string.

    Catches the pattern ``("kept", "Unknown status")`` and similar
    column-name/key-value pairs declared inside function bodies. Files under
    ``config/`` and test files are exempt because that is where named
    constants are expected to live.
    """
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    snake_case_pattern = re.compile(SNAKE_CASE_LITERAL_PATTERN)
    issues: list[str] = []
    seen_tuple_node_ids: set[int] = set()
    for each_function_node in ast.walk(tree):
        if not isinstance(each_function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_body_statement in each_function_node.body:
            for each_descendant in _walk_skipping_nested_function_defs(each_body_statement):
                if not isinstance(each_descendant, ast.Tuple):
                    continue
                if id(each_descendant) in seen_tuple_node_ids:
                    continue
                seen_tuple_node_ids.add(id(each_descendant))
                if len(each_descendant.elts) != EXPECTED_TUPLE_PAIR_LENGTH:
                    continue
                first_element = each_descendant.elts[0]
                if not isinstance(first_element, ast.Constant):
                    continue
                if not isinstance(first_element.value, str):
                    continue
                literal_text = first_element.value
                if not snake_case_pattern.match(literal_text):
                    continue
                if literal_text in ALL_SNAKE_CASE_KEYWORD_EXEMPTIONS:
                    continue
                issues.append(
                    f"Line {first_element.lineno}: Column-name string magic "
                    f"{literal_text!r} - {INLINE_TUPLE_STRING_MAGIC_MESSAGE_SUFFIX}"
                )
                if len(issues) >= MAX_INLINE_TUPLE_STRING_MAGIC_ISSUES:
                    return issues
    return issues


def _is_whitespace_indentation_literal(string_value: str) -> bool:
    if not string_value:
        return False
    if string_value.strip():
        return False
    if "\t" * INDENTATION_MAGIC_MINIMUM_TAB_RUN in string_value:
        return True
    return " " * INDENTATION_MAGIC_MINIMUM_SPACE_RUN in string_value


def check_whitespace_indentation_magic(content: str, file_path: str) -> list[str]:
    """Flag a whitespace-only indentation literal in a function body.

    A string literal that is entirely whitespace and carries a run of at least
    ``INDENTATION_MAGIC_MINIMUM_SPACE_RUN`` spaces, or a run of at least
    ``INDENTATION_MAGIC_MINIMUM_TAB_RUN`` tabs, is a formatting default — the
    indentation an output builder prepends — so it belongs in a
    named constant in ``config/`` that one definition feeds to every call site.
    Both a standalone string constant (``"            "``) and the literal
    fragment of an f-string (``f"\\n            {value}"``) are inspected, so an
    indent embedded beside an interpolation is caught too. Config files, test
    files, workflow-registry files, and migration files are exempt.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per whitespace-only indentation literal found in a function
        body, capped at the module limit.
    """
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    flagged_node_ids: set[int] = set()
    for each_function_node in ast.walk(tree):
        if not isinstance(each_function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_body_statement in each_function_node.body:
            for each_descendant in _walk_skipping_nested_function_defs(each_body_statement):
                if not isinstance(each_descendant, ast.Constant):
                    continue
                if not isinstance(each_descendant.value, str):
                    continue
                if id(each_descendant) in flagged_node_ids:
                    continue
                if not _is_whitespace_indentation_literal(each_descendant.value):
                    continue
                flagged_node_ids.add(id(each_descendant))
                issues.append(
                    f"Line {each_descendant.lineno}: {each_descendant.value!r} "
                    f"{WHITESPACE_INDENTATION_MAGIC_MESSAGE_SUFFIX}"
                )
                if len(issues) >= MAX_WHITESPACE_INDENTATION_MAGIC_ISSUES:
                    return issues
    return issues
