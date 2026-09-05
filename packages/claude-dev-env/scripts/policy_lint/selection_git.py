from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .config.constants import (
    ALL_GIT_BLOB_ARGUMENTS,
    ALL_GIT_HEAD_ARGUMENTS,
    ALL_MISSING_BLOB_ERROR_FRAGMENTS,
    ALL_UNBORN_HEAD_ERROR_FRAGMENTS,
    GIT_ENVIRONMENT_VARIABLE_PREFIX,
    GIT_INDEX_ENVIRONMENT_VARIABLE,
    GIT_EXECUTABLE,
    NUL_BYTE,
    UTF8_ENCODING,
)


class GitSelectionError(ValueError):
    """Raised when Git cannot provide the requested source bytes."""


def git_bytes_for(repository_root: Path, all_arguments: tuple[str, ...]) -> bytes:
    """Run a fixed Git argument vector and return raw stdout bytes.

    Args:
        repository_root: Repository root used as the process directory.
        all_arguments: Git arguments without the executable name.

    Returns:
        Raw Git stdout bytes.

    Raises:
        GitSelectionError: If Git returns a failure status.
    """
    completed = subprocess.run(
        [GIT_EXECUTABLE, *all_arguments],
        cwd=repository_root,
        capture_output=True,
        check=False,
        env=_git_subprocess_environment(),
    )
    if completed.returncode != 0:
        error_text = completed.stderr.decode(UTF8_ENCODING, errors="replace").strip()
        raise GitSelectionError(error_text or "Git command failed")
    return completed.stdout


def head_revision(repository_root: Path) -> str | None:
    """Return the current commit or None for an unborn repository.

    Args:
        repository_root: Repository root used as the process directory.

    Returns:
        The current commit name, or None when HEAD does not exist.

    Raises:
        GitSelectionError: If Git reports an unexpected HEAD failure.
    """
    completed = subprocess.run(
        [GIT_EXECUTABLE, *ALL_GIT_HEAD_ARGUMENTS],
        cwd=repository_root,
        capture_output=True,
        check=False,
        env=_git_subprocess_environment(),
    )
    if completed.returncode != 0:
        error_text = completed.stderr.decode(UTF8_ENCODING, errors="replace").strip()
        if any(
            each_fragment in error_text.casefold()
            for each_fragment in ALL_UNBORN_HEAD_ERROR_FRAGMENTS
        ):
            return None
        raise GitSelectionError(error_text or "Git HEAD lookup failed")
    return completed.stdout.decode(UTF8_ENCODING).strip()


def read_blob(repository_root: Path, revision: str, relative_path: str) -> str | None:
    """Read one Git blob as UTF-8 text.

    Args:
        repository_root: Repository root used as the process directory.
        revision: Commit, tree, or index revision prefix.
        relative_path: Repository-relative path.

    Returns:
        Decoded blob text, or None when the blob is absent.

    Raises:
        GitSelectionError: If the blob is not UTF-8.
    """
    blob_bytes = _read_blob_bytes(repository_root, revision, relative_path)
    if blob_bytes is None:
        return None
    try:
        return blob_bytes.decode(UTF8_ENCODING)
    except UnicodeDecodeError as error:
        raise GitSelectionError(f"Git blob is not UTF-8: {relative_path}") from error


def _git_subprocess_environment() -> dict[str, str]:
    git_prefix = GIT_ENVIRONMENT_VARIABLE_PREFIX
    return {
        each_name: each_environment_text
        for each_name, each_environment_text in os.environ.items()
        if not each_name.upper().startswith(git_prefix)
        or each_name.upper() == GIT_INDEX_ENVIRONMENT_VARIABLE
    }


def _read_blob_bytes(repository_root: Path, revision: str, relative_path: str) -> bytes | None:
    completed = subprocess.run(
        [
            GIT_EXECUTABLE,
            *ALL_GIT_BLOB_ARGUMENTS,
            f"{revision}:{relative_path}",
        ],
        cwd=repository_root,
        capture_output=True,
        check=False,
        env=_git_subprocess_environment(),
    )
    if completed.returncode == 0:
        return completed.stdout
    error_text = completed.stderr.decode(UTF8_ENCODING, errors="replace").strip()
    if any(
        each_fragment in error_text.casefold()
        for each_fragment in ALL_MISSING_BLOB_ERROR_FRAGMENTS
    ):
        return None
    raise GitSelectionError(error_text or "Git blob read failed")


def split_nul_tokens(raw_bytes: bytes) -> tuple[str, ...]:
    """Decode a NUL-separated Git path response.

    Args:
        raw_bytes: NUL-separated Git response bytes.

    Returns:
        Non-empty UTF-8 path tokens.
    """
    return tuple(
        each_token.decode(UTF8_ENCODING)
        for each_token in raw_bytes.split(NUL_BYTE)
        if each_token
    )
