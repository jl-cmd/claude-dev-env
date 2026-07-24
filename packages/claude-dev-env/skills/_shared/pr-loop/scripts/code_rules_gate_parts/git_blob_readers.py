"""Read the committed or staged content of one file from git.

The gate validates staged content against the file's prior committed content, so
these readers return the HEAD blob, the staged blob, and a staged-presence
probe. A missing or non-Unicode blob resolves to an empty string, None, or
False so the caller fails closed rather than crashing.
"""

import subprocess
from pathlib import Path

from terminology_sweep import repository_environment


def read_prior_committed_content(repository_root: Path, relative_path_posix: str) -> str:
    """Return the HEAD-committed content for *relative_path_posix*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to read.

    Returns:
        The committed content at HEAD, or an empty string when the path is not
        tracked or ``git show`` returns non-zero.
    """
    completed = subprocess.run(
        ["git", "show", f"HEAD:{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=repository_environment(),
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout


def read_staged_content(repository_root: Path, relative_path_posix: str) -> str | None:
    """Return the staged-blob content for *relative_path_posix*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to read.

    Returns:
        The staged blob content, or None when the path is not staged, when
        ``git show`` returns non-zero, or when the bytes are not Unicode.
    """
    completed = subprocess.run(
        ["git", "show", f":{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        check=False,
        env=repository_environment(),
    )
    if completed.returncode != 0:
        return None
    try:
        return completed.stdout.decode(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def staged_blob_exists(repository_root: Path, relative_path_posix: str) -> bool:
    """Report whether *relative_path_posix* is present in the staged index.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to probe.

    Returns:
        True when the path's blob exists in the index; False when absent, such
        as a staged deletion.
    """
    completed = subprocess.run(
        ["git", "cat-file", "-e", f":{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        check=False,
        env=repository_environment(),
    )
    return completed.returncode == 0
