"""Report a new code file that nothing outside its own tests calls.

A script, hook or skill script earns its place when something runs it: a
``hooks.json`` entry, a workflow step, a skill or command, or an import from
live code. A file whose only mention is its own test ships work nobody uses.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from .config import constants
from .model import Diagnostic, Document, DocumentSet, Location, SelectionKind, Severity


def _is_test_path(path: PurePosixPath) -> bool:
    return (
        path.name.startswith("test_")
        or path.stem.endswith("_test")
        or ".test." in path.name
        or "tests" in path.parts
        or "test" in path.parts
    )


def _is_new_code_file(document: Document) -> bool:
    if document.prior_text is not None or document.prior_path is not None:
        return False
    path = document.path
    if path.suffix.lower() not in constants.ALL_CALLED_CODE_SUFFIXES:
        return False
    if path.name in constants.ALL_UNCALLED_EXEMPT_FILE_NAMES or _is_test_path(path):
        return False
    normalized_path = f"/{path.as_posix()}"
    return any(
        each_segment in normalized_path
        for each_segment in constants.ALL_CALLED_CODE_SEGMENTS
    )


def _is_caller_source(
    relative_path: PurePosixPath, all_candidate_paths: frozenset[PurePosixPath]
) -> bool:
    if constants.ALL_CALLER_SEARCH_SKIPPED_DIRECTORIES.intersection(
        relative_path.parts
    ):
        return False
    if relative_path.name in constants.ALL_INVENTORY_FILE_NAMES:
        return False
    return relative_path not in all_candidate_paths and not _is_test_path(
        relative_path
    )


def _read_caller_text(file_path: Path) -> str:
    try:
        return file_path.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _caller_texts(
    repository_root: Path, all_candidate_paths: frozenset[PurePosixPath]
) -> tuple[str, ...]:
    return tuple(
        _read_caller_text(each_path)
        for each_path in repository_root.rglob("*")
        if each_path.is_file()
        and _is_caller_source(
            PurePosixPath(each_path.relative_to(repository_root).as_posix()),
            all_candidate_paths,
        )
    )


def _has_caller(document: Document, all_caller_texts: tuple[str, ...]) -> bool:
    name_pattern = re.compile(
        constants.CALLER_NAME_PATTERN_TEMPLATE.format(
            name=re.escape(document.path.stem)
        )
    )
    return any(name_pattern.search(each_text) for each_text in all_caller_texts)


def _reached_paths(
    all_new_documents: tuple[Document, ...],
    all_caller_texts: tuple[str, ...],
    all_called: set[PurePosixPath],
) -> set[PurePosixPath]:
    return {
        each_document.path
        for each_document in all_new_documents
        if each_document.path not in all_called
        and _has_caller(each_document, all_caller_texts)
    }


def _called_paths(
    all_new_documents: tuple[Document, ...], all_caller_texts: tuple[str, ...]
) -> frozenset[PurePosixPath]:
    """Return each new file a caller reaches, directly or through a called new file.

    ::

        workflow step -> new_check.py -> new_check_constants.py   both called
        nothing       -> lonely.py    -> helper.py               both uncalled

    Args:
        all_new_documents: Every new code file in the change.
        all_caller_texts: Text of every existing file that may name one.

    Returns:
        Paths of the new files some caller chain reaches.
    """
    all_called: set[PurePosixPath] = set()
    all_reached = _reached_paths(all_new_documents, all_caller_texts, all_called)
    while all_reached:
        all_called |= all_reached
        all_reached_texts = tuple(
            each_document.text
            for each_document in all_new_documents
            if each_document.path in all_reached
        )
        all_reached = _reached_paths(all_new_documents, all_reached_texts, all_called)
    return frozenset(all_called)


def _uncalled_diagnostic(document: Document) -> Diagnostic:
    return Diagnostic(
        constants.UNCALLED_NEW_FILE_RULE_ID,
        Severity.ERROR,
        constants.UNCALLED_NEW_FILE_MESSAGE.format(file_name=document.path.name),
        Location(document.path, 1, 1),
    )


def uncalled_new_file_diagnostics(
    document_set: DocumentSet,
) -> tuple[Diagnostic, ...]:
    """Report each new code file with no caller outside its tests.

    Args:
        document_set: Staged or base change selection.

    Returns:
        One diagnostic for each added script, hook or skill script whose name
        appears only in tests, inventory files, and other uncalled new files.
    """
    if document_set.selection not in {SelectionKind.STAGED, SelectionKind.BASE}:
        return ()
    all_new_documents = tuple(
        each_document
        for each_document in document_set.documents
        if _is_new_code_file(each_document)
    )
    if not all_new_documents:
        return ()
    all_caller_texts = _caller_texts(
        document_set.repository_root,
        frozenset(each_document.path for each_document in all_new_documents),
    )
    all_called = _called_paths(all_new_documents, all_caller_texts)
    return tuple(
        _uncalled_diagnostic(each_document)
        for each_document in all_new_documents
        if each_document.path not in all_called
    )
