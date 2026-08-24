"""Atomic text replacement for hook-state files."""

import os
import tempfile
from pathlib import Path

from hooks_constants.atomic_file_writer_constants import TEXT_WRITE_MODE


def _remove_orphaned_temporary_files(
    parent_directory: Path, temporary_prefix: str, temporary_suffix: str
) -> None:
    for each_temporary_path in parent_directory.glob(f"{temporary_prefix}*{temporary_suffix}"):
        try:
            each_temporary_path.unlink(missing_ok=True)
        except OSError:
            continue


def _write_temporary_text(
    parent_directory: Path,
    serialized_text: str,
    encoding: str,
    temporary_prefix: str,
    temporary_suffix: str,
) -> Path:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode=TEXT_WRITE_MODE,
            encoding=encoding,
            dir=parent_directory,
            prefix=temporary_prefix,
            suffix=temporary_suffix,
            delete=False,
        ) as writable_handle:
            temporary_path = Path(writable_handle.name)
            writable_handle.write(serialized_text)
        return temporary_path
    except (OSError, UnicodeError):
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def write_text_atomically(
    target_path: Path,
    serialized_text: str,
    encoding: str,
    temporary_prefix: str,
    temporary_suffix: str,
    should_reap_orphans: bool,
) -> None:
    """Replace one text file through a unique sibling temporary file.

    Args:
        target_path: The destination file path.
        serialized_text: The complete replacement text.
        encoding: The text encoding.
        temporary_prefix: Prefix for sibling temporary files.
        temporary_suffix: Suffix for sibling temporary files.
        should_reap_orphans: Whether to remove same-pattern temporary files first.
    """
    parent_directory = target_path.parent
    parent_directory.mkdir(parents=True, exist_ok=True)
    if should_reap_orphans:
        _remove_orphaned_temporary_files(parent_directory, temporary_prefix, temporary_suffix)
    temporary_path = _write_temporary_text(
        parent_directory,
        serialized_text,
        encoding,
        temporary_prefix,
        temporary_suffix,
    )
    try:
        os.replace(temporary_path, target_path)
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
