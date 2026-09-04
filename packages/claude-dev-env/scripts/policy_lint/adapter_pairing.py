from __future__ import annotations

from pathlib import PurePosixPath

from . import adapter_support
from .config import constants
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


def _has_changed_test(
    production_path: PurePosixPath,
    all_changed_test_paths: frozenset[PurePosixPath],
) -> bool:
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
        if _is_unpaired_production(
            each_document, all_changed_test_paths, load_module
        )
    )
