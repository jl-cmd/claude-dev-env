from __future__ import annotations

import ast
from collections import Counter
from pathlib import PurePosixPath

from . import adapter_support
from .config import constants
from .config.approved_test_pairs import APPROVED_TEST_PATHS_BY_PRODUCTION_PATH
from .model import Diagnostic, Document, DocumentSet, Location, SelectionKind, Severity


def _is_test_path(path: PurePosixPath) -> bool:
    normalized_name = path.name.lower()
    normalized_parts = {each_part.lower() for each_part in path.parts}
    return (
        normalized_name.startswith(constants.ALL_TEST_FILE_PREFIXES)
        or normalized_name.endswith(constants.ALL_TEST_FILE_SUFFIXES)
        or ".test." in normalized_name
        or ".spec." in normalized_name
        or bool(normalized_parts.intersection(constants.ALL_TEST_DIRECTORY_NAMES))
    )


def _is_constants_only_python_document(
    document: Document, load_module: adapter_support.HookModuleLoader
) -> bool:
    if document.path.suffix.lower() != constants.PYTHON_SUFFIX:
        return False
    analysis_module = load_module("blocking.tdd_enforcer_parts.content_analysis")
    return analysis_module._is_constants_only_python_content(document.text)


def _is_docstring_statement(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _remove_docstrings(parsed_tree: ast.AST) -> None:
    if (
        isinstance(
            parsed_tree,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and parsed_tree.body
        and _is_docstring_statement(parsed_tree.body[0])
    ):
        parsed_tree.body.pop(0)
    for each_child in ast.iter_child_nodes(parsed_tree):
        _remove_docstrings(each_child)


def _parsed_without_docstrings(source_text: str) -> ast.Module | None:
    try:
        parsed_tree = ast.parse(source_text)
    except (SyntaxError, ValueError):
        return None
    _remove_docstrings(parsed_tree)
    return parsed_tree


def _ast_without_docstrings(source_text: str) -> str | None:
    parsed_tree = _parsed_without_docstrings(source_text)
    if parsed_tree is None:
        return None
    return ast.dump(parsed_tree, include_attributes=False)


def _is_docstring_only_python_document(document: Document) -> bool:
    if document.path.suffix.lower() != constants.PYTHON_SUFFIX:
        return False
    if document.prior_text is None:
        return False
    current_ast = _ast_without_docstrings(document.text)
    prior_ast = _ast_without_docstrings(document.prior_text)
    return current_ast is not None and current_ast == prior_ast


def _is_import_statement(node: object) -> bool:
    return isinstance(node, (ast.Import, ast.ImportFrom))


def _dumped_import_tally(all_nodes: list[object]) -> Counter[str]:
    return Counter(
        ast.dump(each_node, include_attributes=False)
        for each_node in all_nodes
        if isinstance(each_node, ast.AST) and _is_import_statement(each_node)
    )


def _matches_positional_list(
    all_current_nodes: list[object], all_prior_nodes: list[object]
) -> bool:
    if len(all_current_nodes) != len(all_prior_nodes):
        return False
    return all(
        _matches_field(each_current_node, each_prior_node)
        for each_current_node, each_prior_node in zip(
            all_current_nodes, all_prior_nodes, strict=True
        )
    )


def _matches_statement_list(
    all_current_nodes: list[object], all_prior_nodes: list[object]
) -> bool:
    if _dumped_import_tally(all_prior_nodes) - _dumped_import_tally(all_current_nodes):
        return False
    return _matches_positional_list(
        [
            each_node
            for each_node in all_current_nodes
            if not _is_import_statement(each_node)
        ],
        [
            each_node
            for each_node in all_prior_nodes
            if not _is_import_statement(each_node)
        ],
    )


def _is_statement_list(all_nodes: list[object]) -> bool:
    return all(isinstance(each_node, ast.stmt) for each_node in all_nodes)


def _matches_node_list(
    all_current_nodes: list[object], all_prior_nodes: list[object]
) -> bool:
    if _is_statement_list(all_current_nodes) and _is_statement_list(all_prior_nodes):
        return _matches_statement_list(all_current_nodes, all_prior_nodes)
    return _matches_positional_list(all_current_nodes, all_prior_nodes)


def _matches_field(current_field: object, prior_field: object) -> bool:
    if isinstance(current_field, ast.AST) and isinstance(prior_field, ast.AST):
        return _matches_node(current_field, prior_field)
    if isinstance(current_field, list) and isinstance(prior_field, list):
        return _matches_node_list(current_field, prior_field)
    if type(current_field) is not type(prior_field):
        return False
    return bool(current_field == prior_field)


def _matches_keyword(current_keyword: ast.keyword, prior_keyword: ast.keyword) -> bool:
    return current_keyword.arg == prior_keyword.arg and _matches_node(
        current_keyword.value, prior_keyword.value
    )


def _keywords_after_match(
    all_candidate_keywords: list[ast.keyword], prior_keyword: ast.keyword
) -> list[ast.keyword] | None:
    for each_index, each_candidate_keyword in enumerate(all_candidate_keywords):
        if _matches_keyword(each_candidate_keyword, prior_keyword):
            return all_candidate_keywords[each_index + 1 :]
    return None


def _prior_keywords_survive(
    all_current_keywords: list[ast.keyword], all_prior_keywords: list[ast.keyword]
) -> bool:
    all_remaining_keywords: list[ast.keyword] | None = list(all_current_keywords)
    for each_prior_keyword in all_prior_keywords:
        if all_remaining_keywords is None:
            return False
        all_remaining_keywords = _keywords_after_match(
            all_remaining_keywords, each_prior_keyword
        )
    return all_remaining_keywords is not None


def _mapping_unpacking_count(all_keywords: list[ast.keyword]) -> int:
    return sum(1 for each_keyword in all_keywords if each_keyword.arg is None)


def _matches_call(current_call: ast.Call, prior_call: ast.Call) -> bool:
    if not _matches_node(current_call.func, prior_call.func):
        return False
    if not _matches_positional_list(list(current_call.args), list(prior_call.args)):
        return False
    if _mapping_unpacking_count(current_call.keywords) != _mapping_unpacking_count(
        prior_call.keywords
    ):
        return False
    return _prior_keywords_survive(
        list(current_call.keywords), list(prior_call.keywords)
    )


def _matches_node(current_node: ast.AST, prior_node: ast.AST) -> bool:
    if type(current_node) is not type(prior_node):
        return False
    if isinstance(current_node, ast.Call) and isinstance(prior_node, ast.Call):
        return _matches_call(current_node, prior_node)
    return all(
        _matches_field(
            getattr(current_node, each_field_name, None),
            getattr(prior_node, each_field_name, None),
        )
        for each_field_name in current_node._fields
    )


def _is_import_and_keyword_addition_python_document(document: Document) -> bool:
    if document.path.suffix.lower() != constants.PYTHON_SUFFIX:
        return False
    if document.prior_text is None:
        return False
    current_tree = _parsed_without_docstrings(document.text)
    prior_tree = _parsed_without_docstrings(document.prior_text)
    if current_tree is None or prior_tree is None:
        return False
    return _matches_node(current_tree, prior_tree)


def _candidate_test_names(path: PurePosixPath) -> frozenset[str]:
    stem = path.stem
    suffix = path.suffix.lower()
    if suffix == constants.PYTHON_SUFFIX:
        return frozenset({f"test_{stem}.py", f"{stem}_test.py"})
    if suffix in constants.ALL_CODE_SUFFIXES:
        return frozenset({f"{stem}.test{suffix}", f"{stem}.spec{suffix}"})
    return frozenset()


def _family_tokens(path: PurePosixPath) -> tuple[str, ...]:
    normalized_stem = path.stem.lower().replace("-", "_").replace(".", "_")
    normalized_stem = normalized_stem.removeprefix("test_")
    normalized_stem = normalized_stem.removesuffix("_test")
    return tuple(each_token for each_token in normalized_stem.split("_") if each_token)


def _is_policy_lint_test_match(
    production_path: PurePosixPath, test_path: PurePosixPath
) -> bool:
    if constants.POLICY_LINT_DIRECTORY_NAME not in production_path.parts:
        return False
    test_prefix = (
        constants.POLICY_LINT_SELECTION_TEST_PREFIX
        if production_path.stem.lower() in {"selection", "selection_git"}
        else constants.POLICY_LINT_RULES_TEST_PREFIX
    )
    normalized_test_stem = test_path.stem.lower()
    return normalized_test_stem == test_prefix or normalized_test_stem.startswith(
        f"{test_prefix}_"
    )


def _is_grouped_test_match(
    production_path: PurePosixPath, test_path: PurePosixPath
) -> bool:
    if _is_policy_lint_test_match(production_path, test_path):
        return True
    if production_path.stem.lower() in {
        constants.RUN_ALL_VALIDATORS_STEM,
        constants.FAST_SAVE_VALIDATORS_STEM,
    }:
        all_production_tokens = _family_tokens(production_path)
        all_test_tokens = _family_tokens(test_path)
        return all_test_tokens[: len(all_production_tokens)] == all_production_tokens
    return _family_tokens(production_path) == _family_tokens(test_path)


def _has_changed_approved_test(
    production_path: PurePosixPath,
    all_changed_test_paths: frozenset[PurePosixPath],
) -> bool:
    all_approved_test_paths = APPROVED_TEST_PATHS_BY_PRODUCTION_PATH.get(
        production_path, frozenset()
    )
    return not all_approved_test_paths.isdisjoint(all_changed_test_paths)


def _has_changed_test(
    production_path: PurePosixPath,
    all_changed_test_paths: frozenset[PurePosixPath],
) -> bool:
    if _has_changed_approved_test(production_path, all_changed_test_paths):
        return True
    all_candidate_names = _candidate_test_names(production_path)
    return any(
        each_test_path.name.lower() in all_candidate_names
        or _is_grouped_test_match(production_path, each_test_path)
        for each_test_path in all_changed_test_paths
    )


def _is_unpaired_production(
    production_document: Document,
    all_changed_test_paths: frozenset[PurePosixPath],
    load_module: adapter_support.HookModuleLoader,
) -> bool:
    production_path = production_document.path
    if production_path.suffix.lower() not in constants.ALL_CODE_SUFFIXES:
        return False
    if _is_test_path(production_path):
        return False
    if _is_constants_only_python_document(production_document, load_module):
        return False
    if _is_docstring_only_python_document(production_document):
        return False
    if _is_import_and_keyword_addition_python_document(production_document):
        return False
    return not _has_changed_test(production_path, all_changed_test_paths)


def _changed_test_paths(document_set: DocumentSet) -> frozenset[PurePosixPath]:
    return frozenset(
        each_document.path
        for each_document in document_set.documents
        if _is_test_path(each_document.path)
    )


def _pairing_diagnostic(document: Document) -> Diagnostic:
    return Diagnostic(
        "test-pairing",
        Severity.ERROR,
        "Changed production file has no changed matching test",
        Location(document.path, 1, 1),
    )


def test_pairing_diagnostics(
    document_set: DocumentSet,
    load_module: adapter_support.HookModuleLoader,
) -> tuple[Diagnostic, ...]:
    """Report changed production files without a changed matching test.

    Args:
        document_set: Staged or base change selection.
        load_module: Hook module loader.

    Returns:
        Test-pairing diagnostics for unmatched production files.
    """
    if document_set.selection not in {SelectionKind.STAGED, SelectionKind.BASE}:
        return ()
    all_changed_test_paths = _changed_test_paths(document_set)
    return tuple(
        _pairing_diagnostic(each_document)
        for each_document in document_set.documents
        if _is_unpaired_production(each_document, all_changed_test_paths, load_module)
    )
