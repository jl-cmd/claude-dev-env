from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import (
    ALL_GIT_BASE_ARGUMENT_PREFIX,
    ALL_GIT_CHANGED_FILES_ARGUMENTS,
    ALL_GIT_HEAD_ARGUMENTS,
    ALL_GIT_INDEX_CHANGED_FILES_ARGUMENTS,
    ALL_GIT_ROOT_ARGUMENTS,
    ALL_GIT_STATUS_ARGUMENTS,
    ALL_GIT_TREE_ARGUMENTS,
    ALL_GIT_UNTRACKED_FILES_ARGUMENTS,
    DIGEST_BYTE_ORDER,
    DIGEST_LENGTH_BYTES,
    GIT_COMMIT_OBJECT_SUFFIX,
    GIT_EXECUTABLE,
    GIT_PATH_SEPARATOR,
    UTF8_ENCODING,
)
from .config.timing import GIT_METADATA_TIMEOUT_SECONDS


@dataclass(frozen=True)
class CandidateSnapshot:
    head_revision: str | None
    base_revision: str | None
    is_git_repository: bool
    worktree_clean: bool
    input_digest: str | None


def capture_candidate_snapshot(
    repository_path: Path, base_revision: str
) -> CandidateSnapshot:
    """Capture Git revisions and candidate file contents at one point.

    Args:
        repository_path: Candidate repository root.
        base_revision: Base revision supplied to the verification run.

    Returns:
        Git revision and candidate content facts for the snapshot.
    """
    git_root = _run_git_text(repository_path, ALL_GIT_ROOT_ARGUMENTS)
    if git_root is None or Path(git_root).resolve() != repository_path.resolve():
        return CandidateSnapshot(None, None, False, False, None)
    head_revision = _run_git_text(repository_path, ALL_GIT_HEAD_ARGUMENTS)
    resolved_base_revision = _run_git_text(
        repository_path,
        (*ALL_GIT_BASE_ARGUMENT_PREFIX, base_revision + GIT_COMMIT_OBJECT_SUFFIX),
    )
    status_bytes = _run_git_bytes(repository_path, ALL_GIT_STATUS_ARGUMENTS)
    is_worktree_clean = status_bytes == b""
    return CandidateSnapshot(
        head_revision,
        resolved_base_revision,
        True,
        is_worktree_clean,
        _compute_input_digest(repository_path, is_worktree_clean),
    )


def _run_git_text(repository_path: Path, all_arguments: tuple[str, ...]) -> str | None:
    command_bytes = _run_git_bytes(repository_path, all_arguments)
    if command_bytes is None:
        return None
    revision_text = command_bytes.decode(UTF8_ENCODING).strip()
    return revision_text or None


def _run_git_bytes(
    repository_path: Path, all_arguments: tuple[str, ...]
) -> bytes | None:
    try:
        completed_process = subprocess.run(
            [GIT_EXECUTABLE, *all_arguments],
            cwd=repository_path,
            capture_output=True,
            check=False,
            timeout=GIT_METADATA_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed_process.returncode != 0:
        return None
    return completed_process.stdout


def _compute_input_digest(repository_path: Path, is_worktree_clean: bool) -> str | None:
    head_tree = _run_git_text(repository_path, ALL_GIT_TREE_ARGUMENTS)
    if head_tree is None:
        return None
    input_digest = hashlib.sha256()
    _add_digest_record(input_digest, head_tree.encode(UTF8_ENCODING))
    if is_worktree_clean:
        return input_digest.hexdigest()
    all_changed_paths = _changed_input_paths(repository_path)
    if all_changed_paths is None:
        return None
    for each_path_bytes in all_changed_paths:
        input_path = repository_path / Path(each_path_bytes.decode(UTF8_ENCODING))
        input_bytes = _read_input_bytes(input_path)
        if input_bytes is None:
            return None
        _add_digest_record(input_digest, each_path_bytes)
        _add_digest_record(input_digest, input_bytes)
    return input_digest.hexdigest()


def _changed_input_paths(repository_path: Path) -> tuple[bytes, ...] | None:
    all_path_bytes: set[bytes] = set()
    for each_arguments in (
        ALL_GIT_CHANGED_FILES_ARGUMENTS,
        ALL_GIT_INDEX_CHANGED_FILES_ARGUMENTS,
        ALL_GIT_UNTRACKED_FILES_ARGUMENTS,
    ):
        changed_path_bytes = _run_git_bytes(repository_path, each_arguments)
        if changed_path_bytes is None:
            return None
        all_path_bytes.update(
            each_path_bytes
            for each_path_bytes in changed_path_bytes.split(GIT_PATH_SEPARATOR)
            if each_path_bytes
        )
    return tuple(sorted(all_path_bytes))


def _add_digest_record(input_digest: hashlib._Hash, record_bytes: bytes) -> None:
    input_digest.update(
        len(record_bytes).to_bytes(
            DIGEST_LENGTH_BYTES,
            byteorder=DIGEST_BYTE_ORDER,
        )
    )
    input_digest.update(record_bytes)


def _read_input_bytes(input_path: Path) -> bytes | None:
    try:
        return input_path.read_bytes()
    except OSError:
        return None
