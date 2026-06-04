"""Unused module-level import check and its import-range and type-checking-gate helpers."""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_scope_binding import (  # noqa: E402
    _attribute_root_name_if_loaded,
    _collect_string_annotation_names,
    _load_name_is_shadowed,
)
from code_rules_shared import (  # noqa: E402
    _build_parent_map,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.unused_module_import_constants import (  # noqa: E402
    ALL_TYPING_MODULE_NAMES,
    MAX_UNUSED_IMPORT_ISSUES,
    TYPE_CHECKING_IDENTIFIER,
    UNUSED_IMPORT_GUIDANCE,
    line_suppresses_unused_import_via_noqa,
)


def _import_alias_pairs(
    import_node: ast.Import | ast.ImportFrom,
) -> list[tuple[str, int, int | None]]:
    """Return (binding_name, alias_line, from_keyword_line) for each name introduced.

    The from-keyword line is None for plain `import X` statements; for
    `from X import (...)` it carries the line of the `from` keyword so
    callers can honor a `# noqa` placed on the opening line of a
    multi-line import block.
    """
    bindings: list[tuple[str, int, int | None]] = []
    from_keyword_line = import_node.lineno if isinstance(import_node, ast.ImportFrom) else None
    for each_alias in import_node.names:
        if each_alias.name == "*":
            continue
        binding_name = each_alias.asname if each_alias.asname else each_alias.name.split(".")[0]
        alias_line = each_alias.lineno or import_node.lineno
        bindings.append((binding_name, alias_line, from_keyword_line))
    return bindings


def _import_statement_line_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for each_node in tree.body:
        if isinstance(each_node, (ast.Import, ast.ImportFrom)):
            start_line = each_node.lineno
            end_line = each_node.end_lineno or each_node.lineno
            ranges.append((start_line, end_line))
    return ranges


def _line_number_falls_in_import_ranges(
    line_number: int,
    all_import_line_ranges: list[tuple[int, int]],
) -> bool:
    for each_start, each_end in all_import_line_ranges:
        if each_start <= line_number <= each_end:
            return True
    return False


def _type_checking_guard_aliases(tree: ast.Module) -> tuple[set[str], set[str]]:
    all_type_checking_names = {TYPE_CHECKING_IDENTIFIER}
    all_type_checking_module_aliases = set(ALL_TYPING_MODULE_NAMES)
    for each_statement in tree.body:
        if isinstance(each_statement, ast.Import):
            for each_alias in each_statement.names:
                if each_alias.name in ALL_TYPING_MODULE_NAMES:
                    all_type_checking_module_aliases.add(
                        each_alias.asname or each_alias.name
                    )
        elif isinstance(each_statement, ast.ImportFrom):
            if each_statement.module not in ALL_TYPING_MODULE_NAMES:
                continue
            for each_alias in each_statement.names:
                if each_alias.name == TYPE_CHECKING_IDENTIFIER:
                    all_type_checking_names.add(each_alias.asname or each_alias.name)
    return all_type_checking_names, all_type_checking_module_aliases


def _expression_guards_type_checking_block(
    test_expression: ast.expr,
    all_type_checking_names: set[str],
    all_type_checking_module_aliases: set[str],
) -> bool:
    if isinstance(test_expression, ast.Name):
        return test_expression.id in all_type_checking_names
    if isinstance(test_expression, ast.Attribute):
        if test_expression.attr != TYPE_CHECKING_IDENTIFIER:
            return False
        receiver = test_expression.value
        return (
            isinstance(receiver, ast.Name)
            and receiver.id in all_type_checking_module_aliases
        )
    return False


def _module_body_declares_type_checking_gate(tree: ast.Module) -> bool:
    (
        all_type_checking_names,
        all_type_checking_module_aliases,
    ) = _type_checking_guard_aliases(tree)
    return any(
        isinstance(each_statement, ast.If)
        and _expression_guards_type_checking_block(
            each_statement.test,
            all_type_checking_names,
            all_type_checking_module_aliases,
        )
        for each_statement in tree.body
    )


def _collect_load_names_outside_import_ranges(
    tree: ast.Module,
    all_import_line_ranges: list[tuple[int, int]],
) -> set[str]:
    parent_by_node_id = _build_parent_map(tree)
    referenced_names: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Name) and isinstance(each_node.ctx, ast.Load):
            line_number = each_node.lineno
            if line_number is None or _line_number_falls_in_import_ranges(
                line_number,
                all_import_line_ranges,
            ):
                continue
            if _load_name_is_shadowed(each_node, each_node.id, parent_by_node_id):
                continue
            referenced_names.add(each_node.id)
        elif isinstance(each_node, ast.Attribute) and isinstance(
            each_node.ctx, ast.Load
        ):
            line_number = each_node.lineno
            if line_number is None or _line_number_falls_in_import_ranges(
                line_number,
                all_import_line_ranges,
            ):
                continue
            root_name = _attribute_root_name_if_loaded(each_node)
            if root_name is not None and not _load_name_is_shadowed(
                root_name,
                root_name.id,
                parent_by_node_id,
            ):
                referenced_names.add(root_name.id)
    referenced_names.update(_collect_string_annotation_names(tree))
    return referenced_names


def _module_declares_dunder_all(tree: ast.Module) -> bool:
    """Return True when the module body assigns or annotates ``__all__``."""
    return any(
        (
            isinstance(each_node, ast.Assign)
            and any(
                isinstance(each_target, ast.Name) and each_target.id == "__all__"
                for each_target in each_node.targets
            )
        )
        or (
            isinstance(each_node, ast.AnnAssign)
            and isinstance(each_node.target, ast.Name)
            and each_node.target.id == "__all__"
        )
        for each_node in tree.body
    )


def check_unused_module_level_imports(
    content: str,
    file_path: str,
    full_file_content: str | None = None,
) -> list[str]:
    """Flag module-level imports that are never referenced in the rest of the file.

    References are detected from AST ``Name`` / ``Attribute`` loads outside import
    statements so mentions in comments or string literals do not count. Files
    declaring ``__all__`` (including annotated assignments) are skipped. Files
    whose module body includes ``if TYPE_CHECKING:`` (or
    ``typing[._extensions].TYPE_CHECKING``) are skipped. Suppression honors bare
    ``# noqa`` or an explicit ``F401`` code in the noqa list only.

    When ``full_file_content`` is provided, ``content`` is treated as an Edit
    fragment containing the imports being added or replaced, while the
    ``__all__`` / ``TYPE_CHECKING`` gate detection and reference scanning run
    against ``full_file_content`` (the post-edit file as it will look once the
    Edit applies). This prevents false-positive flags on imports added in the
    same Edit as their consumers.
    """
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        fragment_tree = ast.parse(content)
    except SyntaxError:
        return []
    reference_source = full_file_content if full_file_content is not None else content
    try:
        reference_tree = ast.parse(reference_source)
    except SyntaxError:
        return []
    if _module_declares_dunder_all(reference_tree):
        return []
    if _module_body_declares_type_checking_gate(reference_tree):
        return []
    fragment_lines = content.splitlines()
    reference_import_ranges = _import_statement_line_ranges(reference_tree)
    referenced_names = _collect_load_names_outside_import_ranges(
        reference_tree,
        reference_import_ranges,
    )
    import_bindings: list[tuple[str, int, int | None]] = []
    for each_node in fragment_tree.body:
        if isinstance(each_node, (ast.Import, ast.ImportFrom)):
            if isinstance(each_node, ast.ImportFrom) and each_node.module == "__future__":
                continue
            for each_binding in _import_alias_pairs(each_node):
                import_bindings.append(each_binding)
    issues: list[str] = []
    for each_name, each_line_number, each_from_keyword_line in import_bindings:
        if 1 <= each_line_number <= len(fragment_lines):
            if line_suppresses_unused_import_via_noqa(fragment_lines[each_line_number - 1]):
                continue
        if each_from_keyword_line is not None and 1 <= each_from_keyword_line <= len(
            fragment_lines
        ):
            if line_suppresses_unused_import_via_noqa(
                fragment_lines[each_from_keyword_line - 1]
            ):
                continue
        if each_name in referenced_names:
            continue
        issues.append(
            f"Line {each_line_number}: unused module-level import {each_name!r}"
            f" — {UNUSED_IMPORT_GUIDANCE}"
        )
        if len(issues) >= MAX_UNUSED_IMPORT_ISSUES:
            break
    return issues
