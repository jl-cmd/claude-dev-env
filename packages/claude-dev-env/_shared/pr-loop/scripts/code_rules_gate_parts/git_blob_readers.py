"""Read the committed or staged content of one file from git.

The gate validates staged content against the file's prior committed content, so
these readers return the HEAD blob, the staged blob, and a staged-presence
probe. A missing or non-Unicode blob resolves to an empty string, None, or
False so the caller fails closed rather than crashing.

Batch helpers issue one ``git cat-file --batch`` call for a path set and keep
the single-file readers as the fallback for paths the map omits.
"""

import subprocess
from collections.abc import Sequence
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    ALL_GIT_CAT_FILE_BATCH_COMMAND,
    BATCH_STDIN_CARRIAGE_RETURN,
    BATCH_STDIN_LINE_SEPARATOR,
    GIT_BLOB_UTF8_ENCODING,
    GIT_BLOB_UTF8_REPLACE_ERRORS,
    GIT_CAT_FILE_HEADER_MINIMUM_PART_COUNT,
    GIT_CAT_FILE_MISSING_SUFFIX,
    HEAD_BLOB_REQUEST_PREFIX,
    STAGED_BLOB_REQUEST_PREFIX,
    UNIVERSAL_NEWLINE_CR,
    UNIVERSAL_NEWLINE_CRLF,
    UNIVERSAL_NEWLINE_LF,
)
from terminology_sweep import repository_environment


def _decode_head_blob_text(raw_blob: bytes) -> str:
    """Decode a HEAD blob the way ``git show`` with ``text=True`` would.

    ``subprocess.run(..., text=True)`` applies universal newlines, so ``\\r\\n``
    and lone ``\\r`` become ``\\n``. Matching that keeps batch output identical
    to ``read_prior_committed_content``.
    """
    decoded_text = raw_blob.decode(
        encoding=GIT_BLOB_UTF8_ENCODING,
        errors=GIT_BLOB_UTF8_REPLACE_ERRORS,
    )
    return decoded_text.replace(UNIVERSAL_NEWLINE_CRLF, UNIVERSAL_NEWLINE_LF).replace(
        UNIVERSAL_NEWLINE_CR, UNIVERSAL_NEWLINE_LF
    )


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


def _is_safe_for_batch_stdin(relative_path_posix: str) -> bool:
    """Return True when *relative_path_posix* is safe on a line-oriented stdin."""
    return (
        BATCH_STDIN_LINE_SEPARATOR not in relative_path_posix
        and BATCH_STDIN_CARRIAGE_RETURN not in relative_path_posix
    )


def _batchable_relative_paths(all_relative_path_posix: Sequence[str]) -> list[str]:
    """Return unique paths that can ride on line-oriented ``--batch`` stdin."""
    all_unique_paths = list(dict.fromkeys(all_relative_path_posix))
    return [each_path for each_path in all_unique_paths if _is_safe_for_batch_stdin(each_path)]


def _run_git_cat_file_batch(
    repository_root: Path,
    all_request_lines: list[str],
) -> bytes:
    """Return raw ``git cat-file --batch`` stdout for *all_request_lines*."""
    stdin_payload = (
        BATCH_STDIN_LINE_SEPARATOR.join(all_request_lines) + BATCH_STDIN_LINE_SEPARATOR
    ).encode(GIT_BLOB_UTF8_ENCODING)
    completed = subprocess.run(
        list(ALL_GIT_CAT_FILE_BATCH_COMMAND),
        cwd=str(repository_root),
        input=stdin_payload,
        capture_output=True,
        check=False,
        env=repository_environment(),
    )
    if completed.returncode != 0:
        return b""
    return completed.stdout


def _consume_one_batch_entry(stdout: bytes, cursor: int) -> tuple[bytes | None, int]:
    """Parse one ``--batch`` response starting at *cursor*.

    ::

        present:  <oid> <type> <size>\\n<size bytes>\\n  -> (bytes, next)
        missing:  <request> missing\\n                  -> (None, next)

    Args:
        stdout: Full batch stdout bytes.
        cursor: Byte offset of the next response header.

    Returns:
        A pair of the blob bytes (or None when missing) and the next cursor.
    """
    batch_stdout_newline = BATCH_STDIN_LINE_SEPARATOR.encode(GIT_BLOB_UTF8_ENCODING)
    minimum_header_part_count = GIT_CAT_FILE_HEADER_MINIMUM_PART_COUNT
    newline_at = stdout.find(batch_stdout_newline, cursor)
    if newline_at < 0:
        return None, len(stdout)
    header_line = stdout[cursor:newline_at]
    next_cursor = newline_at + 1
    if header_line.endswith(GIT_CAT_FILE_MISSING_SUFFIX):
        return None, next_cursor
    all_header_parts = header_line.split(b" ")
    if len(all_header_parts) < minimum_header_part_count:
        return None, next_cursor
    try:
        blob_size = int(all_header_parts[-1])
    except ValueError:
        return None, next_cursor
    content_end = next_cursor + blob_size
    content_bytes = stdout[next_cursor:content_end]
    next_cursor = content_end
    trailing_newline_end = next_cursor + len(batch_stdout_newline)
    if stdout[next_cursor:trailing_newline_end] == batch_stdout_newline:
        next_cursor = trailing_newline_end
    return content_bytes, next_cursor


def _raw_blob_bytes_for_requests(
    repository_root: Path,
    all_request_lines: list[str],
) -> list[bytes | None]:
    """Return one raw blob (or None when missing) per request line, in order."""
    if not all_request_lines:
        return []
    stdout = _run_git_cat_file_batch(repository_root, all_request_lines)
    if not stdout:
        return [None] * len(all_request_lines)
    all_raw_blobs: list[bytes | None] = []
    cursor = 0
    for each_request in all_request_lines:
        raw_blob, cursor = _consume_one_batch_entry(stdout, cursor)
        all_raw_blobs.append(raw_blob)
    return all_raw_blobs


def read_prior_committed_contents_batch(
    repository_root: Path,
    all_relative_path_posix: Sequence[str],
) -> dict[str, str]:
    """Return HEAD content for each path via one ``git cat-file --batch`` call.

    ::

        present HEAD blob  -> exact committed text (utf-8, errors=replace)
        missing HEAD blob  -> ""  (in-stream " missing" marker, not exit code)
        path with newline  -> omitted from the map (caller falls back)

    Args:
        repository_root: Repository root used as the subprocess working directory.
        all_relative_path_posix: Repository-relative POSIX paths to fetch.

    Returns:
        Mapping from relative path to HEAD content (empty string when missing).
        Paths with an embedded newline are omitted so the single-file reader
        remains the fallback.
    """
    all_batchable_paths = _batchable_relative_paths(all_relative_path_posix)
    all_request_lines = [
        f"{HEAD_BLOB_REQUEST_PREFIX}{each_path}" for each_path in all_batchable_paths
    ]
    all_raw_blobs = _raw_blob_bytes_for_requests(repository_root, all_request_lines)
    content_by_relative_path: dict[str, str] = {}
    for each_path, each_raw_blob in zip(all_batchable_paths, all_raw_blobs, strict=True):
        if each_raw_blob is None:
            content_by_relative_path[each_path] = ""
            continue
        content_by_relative_path[each_path] = _decode_head_blob_text(each_raw_blob)
    return content_by_relative_path


def read_staged_contents_batch(
    repository_root: Path,
    all_relative_path_posix: Sequence[str],
) -> dict[str, str | None]:
    """Return staged content for each path via one ``git cat-file --batch`` call.

    ::

        present UTF-8 blob     -> staged text
        missing staged blob    -> None  (in-stream " missing" marker)
        non-UTF-8 staged blob  -> None  (strict decode, per blob)
        path with newline      -> omitted from the map (caller falls back)

    Args:
        repository_root: Repository root used as the subprocess working directory.
        all_relative_path_posix: Repository-relative POSIX paths to fetch.

    Returns:
        Mapping from relative path to staged text, or None when the blob is
        missing or not valid UTF-8. Paths with an embedded newline are omitted
        so the single-file reader remains the fallback.
    """
    all_batchable_paths = _batchable_relative_paths(all_relative_path_posix)
    all_request_lines = [
        f"{STAGED_BLOB_REQUEST_PREFIX}{each_path}" for each_path in all_batchable_paths
    ]
    all_raw_blobs = _raw_blob_bytes_for_requests(repository_root, all_request_lines)
    content_by_relative_path: dict[str, str | None] = {}
    for each_path, each_raw_blob in zip(all_batchable_paths, all_raw_blobs, strict=True):
        if each_raw_blob is None:
            content_by_relative_path[each_path] = None
            continue
        try:
            content_by_relative_path[each_path] = each_raw_blob.decode(
                encoding=GIT_BLOB_UTF8_ENCODING
            )
        except UnicodeDecodeError:
            content_by_relative_path[each_path] = None
    return content_by_relative_path
