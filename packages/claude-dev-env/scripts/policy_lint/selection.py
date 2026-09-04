from __future__ import annotations

import difflib
import os
from pathlib import Path, PurePosixPath

from .config import constants
from .model import (
    BaseChanges,
    ContentOrigin,
    Document,
    DocumentSet,
    ExplicitFiles,
    LintRequest,
    RepositoryTree,
    SelectionKind,
    StagedChanges,
    TextDocument,
)
from .selection_git import (
    GitSelectionError,
    git_bytes_for,
    head_revision,
    read_blob,
    split_nul_tokens,
)


class SelectionRunFatal(ValueError):
    """Raised when a source selection cannot be resolved safely."""


SelectionError = SelectionRunFatal


def select_documents(request: LintRequest) -> DocumentSet:
    """Resolve one typed request into immutable documents.

    Args:
        request: Source selection and repository root.

    Returns:
        The selected document set.

    Raises:
        SelectionRunFatal: If the source cannot be read safely.
    """
    try:
        repository_root = _validated_repository_root(request.repository_root)
        return _select_source(repository_root, request.source)
    except (GitSelectionError, OSError) as error:
        raise SelectionRunFatal(str(error)) from error


def _select_source(repository_root: Path, source: object) -> DocumentSet:
    if isinstance(source, ExplicitFiles):
        all_documents = tuple(
            _worktree_document(repository_root, each_path) for each_path in source.paths
        )
        return DocumentSet(all_documents, SelectionKind.FILES, repository_root)
    if isinstance(source, StagedChanges):
        return _select_changes(repository_root, True, None)
    if isinstance(source, BaseChanges):
        merge_base = git_bytes_for(
            repository_root,
            (constants.GIT_MERGE_BASE_ARGUMENT, source.revision, constants.GIT_HEAD_REFERENCE),
        ).decode(constants.UTF8_ENCODING).strip()
        return _select_changes(repository_root, False, merge_base)
    if isinstance(source, RepositoryTree):
        return _select_repository_tree(repository_root)
    if isinstance(source, TextDocument):
        normalized_path = _normalize_path(repository_root, source.path)
        document = Document(normalized_path, source.text, None, None, ContentOrigin.EDITOR)
        return DocumentSet((document,), SelectionKind.TEXT, repository_root)
    if isinstance(source, DocumentSet):
        return _normalize_document_set(repository_root, source)
    raise SelectionRunFatal("Unknown source selection")


def _validated_repository_root(repository_root: Path) -> Path:
    resolved_root = repository_root.expanduser().resolve()
    if not resolved_root.is_dir():
        raise SelectionRunFatal(f"Repository root is not a directory: {repository_root}")
    git_root = git_bytes_for(resolved_root, constants.ALL_GIT_ROOT_ARGUMENTS).decode(
        constants.UTF8_ENCODING
    ).strip()
    if resolved_root != Path(git_root).resolve():
        raise SelectionRunFatal(f"Repository root is not the Git root: {git_root}")
    return resolved_root


def _select_repository_tree(repository_root: Path) -> DocumentSet:
    all_documents = tuple(
        _tracked_worktree_document(repository_root, each_path)
        for each_path in _tracked_paths(repository_root)
        if (repository_root / each_path).is_file()
    )
    return DocumentSet(all_documents, SelectionKind.REPOSITORY, repository_root)


def _tracked_worktree_document(repository_root: Path, raw_path: str) -> Document:
    relative_path = _normalize_tracked_path(repository_root, raw_path)
    absolute_path = repository_root.joinpath(*Path(raw_path).parts)
    return Document(
        relative_path,
        _read_worktree_text(absolute_path),
        None,
        None,
        ContentOrigin.WORKTREE,
    )


def _tracked_paths(repository_root: Path) -> tuple[str, ...]:
    raw_paths = git_bytes_for(
        repository_root,
        (constants.GIT_FILES_ARGUMENT, constants.GIT_ZERO_TERMINATED_FLAG),
    )
    return split_nul_tokens(raw_paths)


def _select_changes(
    repository_root: Path,
    is_staged: bool,
    base_revision: str | None,
) -> DocumentSet:
    all_arguments = [constants.GIT_DIFF_ARGUMENT]
    if is_staged:
        all_arguments.append(constants.GIT_CACHED_FLAG)
    if base_revision is not None:
        all_arguments.append(base_revision)
    all_arguments.extend(
        [constants.GIT_NAME_STATUS_FLAG, constants.GIT_FIND_RENAMES_FLAG,
         constants.GIT_ZERO_TERMINATED_FLAG, constants.GIT_SEPARATOR]
    )
    all_records = _parse_change_records(git_bytes_for(repository_root, tuple(all_arguments)))
    return _documents_from_changes(repository_root, all_records, is_staged, base_revision)


def _parse_change_records(raw_bytes: bytes) -> tuple[tuple[str, tuple[str, ...]], ...]:
    all_tokens = raw_bytes.split(constants.NUL_BYTE)
    all_records: list[tuple[str, tuple[str, ...]]] = []
    token_index = 0
    while token_index < len(all_tokens) and all_tokens[token_index]:
        status = all_tokens[token_index].decode(constants.UTF8_ENCODING)
        token_index += 1
        path_count = constants.RENAME_PATH_COUNT if status[:1] in {"R", "C"} else 1
        if token_index + path_count > len(all_tokens):
            raise SelectionRunFatal("Git returned an incomplete path record")
        all_paths = tuple(
            all_tokens[token_index + each_offset].decode(constants.UTF8_ENCODING)
            for each_offset in range(path_count)
        )
        token_index += path_count
        all_records.append((status[:1], all_paths))
    return tuple(all_records)


def _documents_from_changes(
    repository_root: Path,
    all_records: tuple[tuple[str, tuple[str, ...]], ...],
    is_staged: bool,
    base_revision: str | None,
) -> DocumentSet:
    all_documents: list[Document] = []
    all_deleted_paths: list[PurePosixPath] = []
    all_renamed_paths: list[tuple[PurePosixPath, PurePosixPath]] = []
    for each_status, each_paths in all_records:
        _append_change(
            repository_root, each_status, each_paths, is_staged, base_revision,
            all_documents, all_deleted_paths, all_renamed_paths,
        )
    selection_kind = SelectionKind.STAGED if is_staged else SelectionKind.BASE
    return DocumentSet(
        tuple(all_documents), selection_kind, repository_root,
        tuple(all_deleted_paths), tuple(all_renamed_paths),
    )


def _append_change(
    repository_root: Path,
    status: str,
    all_paths: tuple[str, ...],
    is_staged: bool,
    base_revision: str | None,
    all_documents: list[Document],
    all_deleted_paths: list[PurePosixPath],
    all_renamed_paths: list[tuple[PurePosixPath, PurePosixPath]],
) -> None:
    old_path, new_path = all_paths if status[:1] in {"R", "C"} else (all_paths[0], all_paths[0])
    normalized_old_path = _normalize_path(repository_root, old_path)
    normalized_new_path = _normalize_path(repository_root, new_path)
    document = _change_document(
        repository_root, old_path, new_path, normalized_old_path,
        normalized_new_path, is_staged, base_revision, status,
    )
    if document is None:
        all_deleted_paths.append(normalized_old_path)
        return
    all_documents.append(document)
    if document.prior_path is not None:
        all_renamed_paths.append((normalized_old_path, normalized_new_path))


def _change_document(
    repository_root: Path,
    old_path: str,
    new_path: str,
    normalized_old_path: PurePosixPath,
    normalized_new_path: PurePosixPath,
    is_staged: bool,
    base_revision: str | None,
    status: str,
) -> Document | None:
    if status == "D":
        return None
    is_copy = status[:1] == "C"
    is_rename = status[:1] == "R"
    prior_text = _change_prior_text(
        repository_root, old_path, is_staged, base_revision, is_copy
    )
    current_text = _change_current_text(repository_root, new_path, is_staged)
    if current_text is None:
        raise SelectionRunFatal(f"Git blob is unavailable: {new_path}")
    prior_path = normalized_old_path if is_rename else None
    return Document(
        normalized_new_path, current_text, prior_text,
        _changed_lines(prior_text, current_text),
        ContentOrigin.INDEX if is_staged else ContentOrigin.REVISION_DIFF,
        prior_path,
    )


def _change_prior_text(
    repository_root: Path,
    old_path: str,
    is_staged: bool,
    base_revision: str | None,
    is_copy: bool,
) -> str | None:
    prior_revision = head_revision(repository_root) if is_staged else base_revision
    if prior_revision is None or is_copy:
        return None
    return read_blob(repository_root, prior_revision, old_path)


def _change_current_text(
    repository_root: Path, new_path: str, is_staged: bool
) -> str | None:
    if is_staged:
        return read_blob(repository_root, constants.GIT_INDEX_REFERENCE_PREFIX, new_path)
    return _optional_worktree_text(repository_root, new_path)


def _worktree_document(repository_root: Path, file_path: Path) -> Document:
    relative_path = _normalize_path(repository_root, file_path)
    absolute_path = repository_root.joinpath(*relative_path.parts)
    if not absolute_path.is_file():
        raise SelectionRunFatal(f"File does not exist: {file_path}")
    return Document(
        relative_path, _read_worktree_text(absolute_path), None, None,
        ContentOrigin.WORKTREE,
    )


def _optional_worktree_text(repository_root: Path, relative_path: str) -> str | None:
    normalized_path = _normalize_path(repository_root, relative_path)
    absolute_path = repository_root.joinpath(*normalized_path.parts)
    if not absolute_path.is_file():
        return None
    return _read_worktree_text(absolute_path)


def _read_worktree_text(file_path: Path) -> str:
    try:
        return file_path.read_bytes().decode(constants.UTF8_ENCODING)
    except UnicodeDecodeError as error:
        raise SelectionRunFatal(f"File is not UTF-8: {file_path}") from error
    except OSError as error:
        raise SelectionRunFatal(f"File cannot be read: {file_path}") from error


def _normalize_path(
    repository_root: Path, file_path: Path | PurePosixPath | str
) -> PurePosixPath:
    candidate_path = Path(file_path)
    absolute_path = candidate_path if candidate_path.is_absolute() else repository_root / candidate_path
    resolved_path = absolute_path.resolve(strict=False)
    try:
        relative_path = resolved_path.relative_to(repository_root)
    except ValueError as error:
        raise SelectionRunFatal(f"Path is outside the repository: {file_path}") from error
    if relative_path == Path():
        raise SelectionRunFatal(f"Path is the repository root: {file_path}")
    return PurePosixPath(relative_path.as_posix().replace(os.sep, constants.PATH_SEPARATOR))


def _normalize_tracked_path(repository_root: Path, raw_path: str) -> PurePosixPath:
    candidate_path = Path(raw_path)
    if candidate_path.is_absolute():
        raise SelectionRunFatal(f"Tracked path is not relative: {raw_path}")
    resolved_path = (repository_root / candidate_path).resolve(strict=False)
    try:
        resolved_path.relative_to(repository_root)
    except ValueError as error:
        raise SelectionRunFatal(f"Tracked path is outside the repository: {raw_path}") from error
    if candidate_path == Path():
        raise SelectionRunFatal(f"Tracked path is the repository root: {raw_path}")
    return PurePosixPath(raw_path.replace("\\", constants.PATH_SEPARATOR))


def _normalize_document(document: Document, repository_root: Path) -> Document:
    prior_path = (
        None
        if document.prior_path is None
        else _normalize_path(repository_root, document.prior_path)
    )
    return Document(
        _normalize_path(repository_root, document.path),
        document.text,
        document.prior_text,
        document.changed_lines,
        document.origin,
        prior_path,
    )


def _normalize_renamed_path(
    repository_root: Path,
    all_renamed_path: tuple[PurePosixPath, PurePosixPath],
) -> tuple[PurePosixPath, PurePosixPath]:
    old_path, new_path = all_renamed_path
    return (
        _normalize_path(repository_root, old_path),
        _normalize_path(repository_root, new_path),
    )


def _normalize_document_set(repository_root: Path, document_set: DocumentSet) -> DocumentSet:
    all_documents = tuple(
        _normalize_document(each_document, repository_root)
        for each_document in document_set.documents
    )
    all_deleted_paths = tuple(
        _normalize_path(repository_root, each_path)
        for each_path in document_set.deleted_paths
    )
    all_renamed_paths = tuple(
        _normalize_renamed_path(repository_root, each_path)
        for each_path in document_set.renamed_paths
    )
    return DocumentSet(
        all_documents,
        document_set.selection,
        repository_root,
        all_deleted_paths,
        all_renamed_paths,
    )


def _changed_lines(prior_text: str | None, current_text: str) -> frozenset[int] | None:
    if prior_text is None:
        return frozenset(
            range(constants.NEW_DOCUMENT_ORIGIN_LINE, len(current_text.splitlines()) + 1)
        )
    matcher = difflib.SequenceMatcher(
        a=prior_text.splitlines(), b=current_text.splitlines(), autojunk=False
    )
    all_changed_lines: set[int] = set()
    for each_tag, _, _, each_start, each_end in matcher.get_opcodes():
        if each_tag in constants.ALL_DIFF_CHANGED_TAGS:
            all_changed_lines.update(range(each_start + 1, each_end + 1))
    return frozenset(all_changed_lines)
