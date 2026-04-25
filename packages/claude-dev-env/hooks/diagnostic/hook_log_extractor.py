#!/usr/bin/env python3
"""Extract hook-firing records from per-session JSONL transcripts into Neon.

Reads JSONL transcripts at ``PROJECTS_TRANSCRIPT_ROOT`` and ingests only
``attachment`` records whose inner ``attachment.type`` is one of the
five variants enumerated in ``OUTCOME_BY_ATTACHMENT_TYPE``
(``hook_success``, ``hook_blocking_error``, ``hook_non_blocking_error``,
``hook_system_message``, ``hook_additional_context``). Unknown
``hook_``-prefixed variants are skipped until
``OUTCOME_BY_ATTACHMENT_TYPE`` is extended to cover them. Each ingested
record becomes one row in the ``hook_events`` table. Idempotence is
enforced at the database layer via a UNIQUE constraint on
``(source_jsonl_path, source_line_number)`` combined with
``ON CONFLICT DO NOTHING``. Per-file byte offsets in
``OFFSET_STATE_FILE`` skip re-reading unchanged bytes.

Offline graceful behavior: ``psycopg.OperationalError`` or any
connect-time failure appends one ISO-8601 line to
``OFFLINE_WARNING_LOG`` and exits 0, so the Stop hook never blocks
session end on a missing network.
"""

from __future__ import annotations

import contextlib
import datetime
import errno
import glob
import io
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import IO, Iterator, Optional, Sequence

if os.name == "nt":
    try:
        import msvcrt
    except ImportError:
        msvcrt = None
    fcntl = None
else:
    try:
        import fcntl
    except ImportError:
        fcntl = None
    msvcrt = None

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import psycopg
except ImportError:
    psycopg = None

from config.hook_log_extractor_constants import (
    ATTACHMENT_TYPE_HOOK_ADDITIONAL_CONTEXT,
    ATTACHMENT_TYPE_HOOK_BLOCKING_ERROR,
    ATTACHMENT_TYPE_HOOK_SUCCESS,
    ATTACHMENT_TYPE_HOOK_SYSTEM_MESSAGE,
    ATTACHMENT_TYPE_PREFIX,
    BYTE_OFFSET_KEY,
    CATEGORY_PATH_MINIMUM_PARTS,
    COMMAND_EXCERPT_MAX_CHARACTERS,
    CONNECT_TIMEOUT_SECONDS,
    DEFAULT_QUERY_FOR_SUMMARY,
    EMPTY_STRING,
    EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING,
    EXIT_CODE_SUCCESS,
    EXIT_CODE_UNKNOWN_QUERY,
    FLAG_FULL_REBUILD,
    FLAG_INCREMENTAL,
    FLAG_QUERY,
    FLAG_SUMMARY,
    HOOK_CATEGORY_UNCATEGORIZED,
    HOOK_EVENTS_INSERT_SQL,
    HOOK_EVENTS_TRUNCATE_SQL,
    HOOK_NAME_TOOL_SEPARATOR,
    HOOKS_DIRECTORY_TOKEN,
    INSERT_BATCH_SIZE,
    INVALID_QUERY_NAME_MESSAGE_PREFIX,
    JSONL_FILE_GLOB,
    KNOWN_HOOK_CATEGORIES,
    LEGACY_OFFSETS_FORMAT_WARNING_LABEL,
    LINE_NUMBER_KEY,
    LOCK_MAXIMUM_RETRY_COUNT,
    LOCK_RETRY_SLEEP_SECONDS,
    MISSING_NEON_DATABASE_URL_WARNING_LABEL,
    MISSING_PSYCOPG_WARNING_LABEL,
    NEON_DATABASE_URL_ENVIRONMENT_VARIABLE,
    NEWLINE_JOINER,
    OFFLINE_WARNING_LOG,
    OFFSET_STATE_FILE,
    OFFSETS_JSON_INDENT,
    OUTCOME_BY_ATTACHMENT_TYPE,
    PROJECTS_TRANSCRIPT_ROOT,
    QUERIES_DIRECTORY_NAME,
    QUERY_NAME_PATTERN,
    QUERY_NO_ROWS_RETURNED_MESSAGE,
    SCRIPT_PATH_PYTHON_PREFIXES,
    SQL_FILE_EXTENSION,
    STDERR_EXCERPT_MAX_CHARACTERS,
    STDOUT_EXCERPT_MAX_CHARACTERS,
    SUMMARY_COLUMN_HEADINGS,
    SUMMARY_NO_NEW_BLOCKS_MESSAGE,
    SUMMARY_TABLE_COLUMN_GAP,
    TOP_BLOCKED_COMMAND_PREVIEW_MAX_CHARACTERS,
    TOP_BLOCKERS_LAST_24_HOURS_SQL,
    TOP_LEVEL_ATTACHMENT_TYPE,
    UNKNOWN_QUERY_MESSAGE_PREFIX,
)


class MissingNeonDatabaseUrlError(RuntimeError):
    """Raised when the Neon connection URL environment variable is unset."""


class MissingPsycopgDependencyError(RuntimeError):
    """Raised when the psycopg driver is not installed in the interpreter."""


def derive_category(script_path: Optional[str]) -> str:
    """Return the category parent-directory name for a script path."""
    if not script_path:
        return HOOK_CATEGORY_UNCATEGORIZED
    normalized_path = script_path.replace("\\", "/")
    for each_prefix in SCRIPT_PATH_PYTHON_PREFIXES:
        if normalized_path.startswith(each_prefix):
            normalized_path = normalized_path[len(each_prefix) :]
            break
    hooks_directory_token_index = normalized_path.rfind(HOOKS_DIRECTORY_TOKEN)
    if hooks_directory_token_index == -1:
        return HOOK_CATEGORY_UNCATEGORIZED
    remainder_after_hooks_segment = normalized_path[
        hooks_directory_token_index + len(HOOKS_DIRECTORY_TOKEN) :
    ]
    all_remainder_parts = remainder_after_hooks_segment.split("/")
    if len(all_remainder_parts) < CATEGORY_PATH_MINIMUM_PARTS:
        return HOOK_CATEGORY_UNCATEGORIZED
    candidate_category = all_remainder_parts[0]
    if candidate_category in KNOWN_HOOK_CATEGORIES:
        return candidate_category
    return HOOK_CATEGORY_UNCATEGORIZED


def derive_outcome(attachment_type: str) -> str:
    """Map an attachment.type value to its outcome label."""
    return OUTCOME_BY_ATTACHMENT_TYPE[attachment_type]


def extract_script_path(attachment: dict[str, object]) -> Optional[str]:
    """Return the script path embedded in a hook attachment, if any."""
    attachment_type = attachment.get("type", EMPTY_STRING)
    if attachment_type == ATTACHMENT_TYPE_HOOK_SUCCESS:
        return _strip_python_prefix(attachment.get("command"))
    if attachment_type == ATTACHMENT_TYPE_HOOK_BLOCKING_ERROR:
        blocking_error_block = attachment.get("blockingError") or {}
        if isinstance(blocking_error_block, dict):
            return _strip_python_prefix(blocking_error_block.get("command"))
    return None


def _strip_python_prefix(command_string: Optional[str]) -> Optional[str]:
    if not command_string:
        return None
    for each_prefix in SCRIPT_PATH_PYTHON_PREFIXES:
        if command_string.startswith(each_prefix):
            return command_string[len(each_prefix) :]
    return command_string


def extract_tool_name(hook_name: Optional[str]) -> Optional[str]:
    """Return the tool name after the colon in a hook name, if present."""
    if not hook_name:
        return None
    if HOOK_NAME_TOOL_SEPARATOR not in hook_name:
        return None
    return hook_name.split(HOOK_NAME_TOOL_SEPARATOR, 1)[1]


def truncate_command_excerpt(command_text: Optional[str]) -> Optional[str]:
    """Truncate a command string to the configured excerpt budget."""
    return _truncate_to_length(command_text, COMMAND_EXCERPT_MAX_CHARACTERS)


def truncate_stdout_excerpt(stdout_text: Optional[str]) -> Optional[str]:
    """Truncate a stdout string to the configured excerpt budget."""
    return _truncate_to_length(stdout_text, STDOUT_EXCERPT_MAX_CHARACTERS)


def truncate_stderr_excerpt(stderr_text: Optional[str]) -> Optional[str]:
    """Truncate a stderr string to the configured excerpt budget."""
    return _truncate_to_length(stderr_text, STDERR_EXCERPT_MAX_CHARACTERS)


def _truncate_to_length(
    text_or_none: Optional[str], maximum_length: int
) -> Optional[str]:
    if text_or_none is None:
        return None
    if len(text_or_none) <= maximum_length:
        return text_or_none
    return text_or_none[:maximum_length]


def _normalize_content_to_text(content_or_none: object) -> Optional[str]:
    if content_or_none is None:
        return None
    if isinstance(content_or_none, str):
        return content_or_none
    if isinstance(content_or_none, list):
        all_string_items = [
            each_entry for each_entry in content_or_none if isinstance(each_entry, str)
        ]
        return NEWLINE_JOINER.join(all_string_items) if all_string_items else None
    return str(content_or_none)


def build_row_from_attachment(
    parsed_record: dict[str, object],
    source_jsonl_path: str,
    source_line_number: int,
) -> dict[str, object]:
    """Build a hook_events row dict from one parsed JSONL record."""
    attachment_block = parsed_record.get("attachment") or {}
    attachment_type = attachment_block.get("type", EMPTY_STRING)
    outcome_label = derive_outcome(attachment_type)
    script_path_or_none = extract_script_path(attachment_block)
    hook_category_label = derive_category(script_path_or_none)
    hook_name_string = attachment_block.get("hookName")
    hook_event_string = attachment_block.get("hookEvent", EMPTY_STRING)
    tool_use_id_or_none = attachment_block.get("toolUseID")
    tool_name_or_none = extract_tool_name(hook_name_string)

    command_text_or_none = attachment_block.get("command")
    stdout_text_or_none: Optional[str] = attachment_block.get("stdout")
    stderr_text_or_none: Optional[str] = attachment_block.get("stderr")
    exit_code_or_none = attachment_block.get("exitCode")
    duration_milliseconds_or_none = attachment_block.get("durationMs")

    if attachment_type == ATTACHMENT_TYPE_HOOK_BLOCKING_ERROR:
        blocking_error_block = attachment_block.get("blockingError") or {}
        if isinstance(blocking_error_block, dict):
            command_text_or_none = blocking_error_block.get("command")
            blocking_error_message = blocking_error_block.get("blockingError")
            if blocking_error_message:
                stderr_text_or_none = blocking_error_message
    elif attachment_type == ATTACHMENT_TYPE_HOOK_SYSTEM_MESSAGE:
        stdout_text_or_none = _normalize_content_to_text(
            attachment_block.get("content")
        )
    elif attachment_type == ATTACHMENT_TYPE_HOOK_ADDITIONAL_CONTEXT:
        stdout_text_or_none = _normalize_content_to_text(
            attachment_block.get("content")
        )

    return {
        "event_timestamp": parsed_record.get("timestamp"),
        "session_id": parsed_record.get("sessionId", EMPTY_STRING),
        "cwd": parsed_record.get("cwd"),
        "git_branch": parsed_record.get("gitBranch"),
        "hook_event": hook_event_string,
        "hook_name": hook_name_string or EMPTY_STRING,
        "hook_category": hook_category_label,
        "script_path": script_path_or_none,
        "tool_name": tool_name_or_none,
        "tool_use_id": tool_use_id_or_none,
        "outcome": outcome_label,
        "exit_code": exit_code_or_none,
        "duration_ms": duration_milliseconds_or_none,
        "command_excerpt": truncate_command_excerpt(command_text_or_none),
        "stdout_excerpt": truncate_stdout_excerpt(stdout_text_or_none),
        "stderr_excerpt": truncate_stderr_excerpt(stderr_text_or_none),
        "source_jsonl_path": source_jsonl_path,
        "source_line_number": source_line_number,
    }


class AttachmentRecordIterator:
    """Iterates hook attachment records and tracks bytes actually consumed.

    ``final_line_number`` reflects the number of lines read from the file
    (including malformed and non-attachment lines), not just the line
    number of the last yielded record. ``final_byte_offset`` reflects the
    byte position after the last successfully-read line (or
    ``start_offset`` when the file did not exist). ``drained`` is True
    once iteration reached EOF. Callers persist ``final_byte_offset``
    and ``final_line_number`` whenever ``drained`` is True so resumption
    starts from the exact position after the last bytes the iterator
    consumed.
    """

    def __init__(
        self,
        jsonl_file_path: str,
        start_offset: int,
        start_line_number: int = 0,
    ) -> None:
        self._jsonl_file_path = jsonl_file_path
        self._start_offset = start_offset
        self._start_line_number = start_line_number
        self.final_line_number = start_line_number
        self.final_byte_offset = start_offset
        self.drained = False

    def __iter__(self) -> Iterator[tuple[dict[str, object], int, int]]:
        try:
            jsonl_file_handle = io.open(self._jsonl_file_path, "rb")
        except (FileNotFoundError, OSError):
            self.final_line_number = self._start_line_number
            self.final_byte_offset = self._start_offset
            self.drained = True
            return
        with jsonl_file_handle:
            if self._start_offset > 0:
                jsonl_file_handle.seek(self._start_offset)
            current_line_number = self._start_line_number
            current_byte_offset = jsonl_file_handle.tell()
            self.final_byte_offset = current_byte_offset
            while True:
                raw_bytes = jsonl_file_handle.readline()
                if not raw_bytes:
                    self.final_line_number = current_line_number
                    self.final_byte_offset = current_byte_offset
                    self.drained = True
                    return
                current_line_number += 1
                current_byte_offset += len(raw_bytes)
                self.final_line_number = current_line_number
                self.final_byte_offset = current_byte_offset
                try:
                    parsed_record = json.loads(raw_bytes.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(parsed_record, dict):
                    continue
                if parsed_record.get("type") != TOP_LEVEL_ATTACHMENT_TYPE:
                    continue
                attachment_block = parsed_record.get("attachment") or {}
                if not isinstance(attachment_block, dict):
                    continue
                attachment_type = attachment_block.get("type", EMPTY_STRING)
                if not isinstance(attachment_type, str):
                    continue
                if not attachment_type.startswith(ATTACHMENT_TYPE_PREFIX):
                    continue
                if attachment_type not in OUTCOME_BY_ATTACHMENT_TYPE:
                    continue
                yield parsed_record, current_line_number, current_byte_offset


def iter_attachment_records_from_file(
    jsonl_file_path: str,
    start_offset: int,
    start_line_number: int = 0,
) -> AttachmentRecordIterator:
    """Return an iterator over hook attachment records in a JSONL file.

    The returned object supports iteration and exposes
    ``final_line_number`` after iteration completes. ``final_line_number``
    is the total number of lines consumed (malformed and non-attachment
    lines included), which differs from the line number of the last
    yielded record when non-attachment lines trail the last attachment.
    """
    return AttachmentRecordIterator(
        jsonl_file_path=jsonl_file_path,
        start_offset=start_offset,
        start_line_number=start_line_number,
    )


def load_offsets(state_file_path: str) -> dict[str, dict[str, int]]:
    """Load per-file ``{byte_offset, line_number}`` entries from disk.

    Returns an empty dict when the state file is missing or contains
    malformed JSON. Legacy bare-integer entries trigger a single
    offline-warning line and are treated as invalid so the caller
    re-extracts from the start of each file.
    """
    if not os.path.exists(state_file_path):
        return {}
    try:
        with io.open(state_file_path, "r", encoding="utf-8") as state_file_handle:
            loaded_content = json.load(state_file_handle)
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded_content, dict):
        return {}
    migrated_offsets: dict[str, dict[str, int]] = {}
    has_legacy_entries = False
    for each_path, each_entry in loaded_content.items():
        path_string = str(each_path)
        if isinstance(each_entry, dict):
            byte_offset_value = each_entry.get(BYTE_OFFSET_KEY)
            line_number_value = each_entry.get(LINE_NUMBER_KEY)
            if isinstance(byte_offset_value, int) and isinstance(
                line_number_value, int
            ):
                migrated_offsets[path_string] = {
                    BYTE_OFFSET_KEY: byte_offset_value,
                    LINE_NUMBER_KEY: line_number_value,
                }
                continue
        has_legacy_entries = True
    if has_legacy_entries:
        _append_legacy_offsets_warning_line()
    return migrated_offsets


def save_offsets(
    state_file_path: str,
    offset_by_jsonl_path: dict[str, dict[str, int]],
) -> None:
    """Persist per-file offset entries atomically via tempfile + os.replace."""
    state_file_parent = os.path.dirname(state_file_path)
    if state_file_parent:
        os.makedirs(state_file_parent, exist_ok=True)
    temporary_file_handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=state_file_parent or None,
        delete=False,
    )
    temporary_file_path = temporary_file_handle.name
    try:
        try:
            json.dump(
                offset_by_jsonl_path,
                temporary_file_handle,
                indent=OFFSETS_JSON_INDENT,
                sort_keys=True,
            )
            temporary_file_handle.flush()
            os.fsync(temporary_file_handle.fileno())
        finally:
            temporary_file_handle.close()
        os.replace(temporary_file_path, state_file_path)
    except Exception:
        try:
            os.unlink(temporary_file_path)
        except OSError:
            pass
        raise


@contextlib.contextmanager
def _acquire_offsets_lock(state_file_path: str) -> Iterator[None]:
    """Hold a cross-platform advisory lock around an offsets read-modify-write.

    Serializes concurrent extractor runs so two Claude Code sessions
    closing at once cannot clobber each other's offset updates. Uses
    ``msvcrt.locking`` on Windows and ``fcntl.flock`` on POSIX; falls
    back to no locking on platforms where neither module is available.

    The sidecar path ``state_file_path + ".lock"`` is intentional,
    permanent infrastructure. It is a byte-range-lockable companion to
    the offsets file and is deliberately never unlinked. Attempting to
    unlink it after release would open a TOCTOU window on Windows,
    where another process may still hold it open. The stable sidecar
    is the safer choice; reused on every run, its presence in the
    state directory is expected and carries no other meaning.
    """
    lock_file_path = state_file_path + ".lock"
    lock_parent_directory = os.path.dirname(lock_file_path)
    if lock_parent_directory:
        os.makedirs(lock_parent_directory, exist_ok=True)
    lock_file_handle = io.open(lock_file_path, "a+", encoding="utf-8")
    try:
        _lock_file_handle_blocking(lock_file_handle)
        try:
            yield
        finally:
            _unlock_file_handle(lock_file_handle)
    finally:
        lock_file_handle.close()


def _lock_file_handle_blocking(lock_file_handle: IO[str]) -> None:
    """Acquire an exclusive byte-range lock with a bounded retry budget.

    Both the Windows (``msvcrt.locking``) and POSIX (``fcntl.flock``)
    branches deliberately fail fast: Windows uses ``LK_NBLCK`` instead
    of ``LK_LOCK`` so the kernel never blocks ~10s internally, and
    POSIX pairs ``LOCK_EX`` with ``LOCK_NB`` so ``EWOULDBLOCK`` bubbles
    up immediately. The Python ``time.sleep(LOCK_RETRY_SLEEP_SECONDS)``
    between attempts is the sole pacing mechanism, keeping the total
    retry budget within the intended ``LOCK_MAXIMUM_RETRY_COUNT *
    LOCK_RETRY_SLEEP_SECONDS`` window so the caller never exceeds the
    30s Stop hook timeout under sustained contention.
    """
    if msvcrt is not None:
        lock_byte_count = 1
        for _each_attempt_index in range(LOCK_MAXIMUM_RETRY_COUNT):
            try:
                msvcrt.locking(
                    lock_file_handle.fileno(), msvcrt.LK_NBLCK, lock_byte_count
                )
                return
            except OSError as lock_exception:
                if lock_exception.errno != errno.EACCES:
                    raise
                time.sleep(LOCK_RETRY_SLEEP_SECONDS)
        raise OSError(
            errno.EACCES,
            "offsets lock retry budget exhausted",
        )
    if fcntl is not None:
        for _each_attempt_index in range(LOCK_MAXIMUM_RETRY_COUNT):
            try:
                fcntl.flock(
                    lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                )
                return
            except OSError as lock_exception:
                if lock_exception.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    raise
                time.sleep(LOCK_RETRY_SLEEP_SECONDS)
        raise OSError(
            errno.EWOULDBLOCK,
            "offsets lock retry budget exhausted",
        )


def _unlock_file_handle(lock_file_handle: IO[str]) -> None:
    if msvcrt is not None:
        lock_byte_count = 1
        try:
            msvcrt.locking(
                lock_file_handle.fileno(), msvcrt.LK_UNLCK, lock_byte_count
            )
        except OSError:
            return
        return
    if fcntl is not None:
        fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_UN)


def is_operational_error(exception_instance: BaseException) -> bool:
    """Return True when an exception should trigger the offline fallback."""
    if isinstance(
        exception_instance,
        (MissingNeonDatabaseUrlError, MissingPsycopgDependencyError),
    ):
        return True
    class_name = type(exception_instance).__name__
    return class_name in {"OperationalError", "InterfaceError", "TimeoutError"}


def connect_to_neon() -> object:
    """Open a psycopg connection using the Neon database URL env var.

    Raises ``MissingNeonDatabaseUrlError`` when the URL env var is unset
    and ``MissingPsycopgDependencyError`` when psycopg is not installed.
    Both are treated as offline by ``is_operational_error`` so the Stop
    hook never blocks session end on a missing environment.
    """
    if psycopg is None:
        raise MissingPsycopgDependencyError(MISSING_PSYCOPG_WARNING_LABEL)
    raw_database_url = os.environ.get(NEON_DATABASE_URL_ENVIRONMENT_VARIABLE)
    database_url = raw_database_url.strip() if raw_database_url is not None else None
    if not database_url:
        raise MissingNeonDatabaseUrlError(MISSING_NEON_DATABASE_URL_WARNING_LABEL)
    return psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS)


def insert_rows_batch(
    neon_connection: object,
    all_rows: Sequence[dict[str, object]],
) -> None:
    """Insert a batch of hook_events rows with ON CONFLICT DO NOTHING."""
    if not all_rows:
        return
    with neon_connection.cursor() as neon_cursor:
        neon_cursor.executemany(HOOK_EVENTS_INSERT_SQL, list(all_rows))
    neon_connection.commit()


def _append_offline_warning_line(exception_instance: BaseException) -> None:
    """Append an offline-marker line to the warning log; swallow disk errors.

    The Stop hook contract requires that the offline-graceful path
    always exits with ``EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING`` so
    session shutdown never stalls on a failed extractor. A read-only
    filesystem, missing parent path, or EACCES on the warning log file
    itself must not propagate to the caller.
    """
    try:
        warning_log_parent = os.path.dirname(OFFLINE_WARNING_LOG)
        if warning_log_parent:
            os.makedirs(warning_log_parent, exist_ok=True)
        timestamp_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        exception_class_name = type(exception_instance).__name__
        warning_line_text = f"{timestamp_iso}\toffline\t{exception_class_name}"
        with io.open(OFFLINE_WARNING_LOG, "a", encoding="utf-8") as warning_log_handle:
            warning_log_handle.write(warning_line_text + "\n")
    except OSError:
        return


def _append_legacy_offsets_warning_line() -> None:
    try:
        warning_log_parent = os.path.dirname(OFFLINE_WARNING_LOG)
        if warning_log_parent:
            os.makedirs(warning_log_parent, exist_ok=True)
        timestamp_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        warning_line_text = (
            f"{timestamp_iso}\tmigration\t{LEGACY_OFFSETS_FORMAT_WARNING_LABEL}"
        )
        with io.open(OFFLINE_WARNING_LOG, "a", encoding="utf-8") as warning_log_handle:
            warning_log_handle.write(warning_line_text + "\n")
    except OSError:
        return


def run_full_extraction(
    transcripts_root: str,
    state_file_path: str,
    full_rebuild: bool,
) -> int:
    """Execute one extraction pass (incremental by default).

    The offsets lock is held only around the initial offsets load and
    around each offsets write (where the latest on-disk offsets are
    re-read and merged with this process's pending updates via a
    per-file max). DB I/O and JSONL iteration run without the lock so
    concurrent Stop hooks do not serialize on each other's slow work.

    Returns process exit code (0 on success, 0 on offline fallback).
    """
    try:
        neon_connection = connect_to_neon()
    except Exception as connect_exception:
        if is_operational_error(connect_exception):
            _append_offline_warning_line(connect_exception)
            return EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING
        raise

    try:
        starting_offset_by_jsonl_path = _load_starting_offsets(
            neon_connection=neon_connection,
            state_file_path=state_file_path,
            full_rebuild=full_rebuild,
        )

        all_jsonl_file_paths = _discover_jsonl_files(transcripts_root)
        for each_jsonl_file_path in all_jsonl_file_paths:
            previous_entry = starting_offset_by_jsonl_path.get(each_jsonl_file_path)
            start_offset = (
                previous_entry[BYTE_OFFSET_KEY]
                if previous_entry is not None
                else 0
            )
            start_line_number = (
                previous_entry[LINE_NUMBER_KEY]
                if previous_entry is not None
                else 0
            )
            batch_buffer: list[dict[str, object]] = []
            attachment_iterator = iter_attachment_records_from_file(
                each_jsonl_file_path,
                start_offset=start_offset,
                start_line_number=start_line_number,
            )
            for (
                parsed_record,
                line_number,
                byte_offset_after,
            ) in attachment_iterator:
                built_row = build_row_from_attachment(
                    parsed_record=parsed_record,
                    source_jsonl_path=each_jsonl_file_path,
                    source_line_number=line_number,
                )
                batch_buffer.append(built_row)
                if len(batch_buffer) >= INSERT_BATCH_SIZE:
                    insert_rows_batch(neon_connection, batch_buffer)
                    batch_buffer.clear()
                    _merge_and_save_offsets_under_lock(
                        state_file_path=state_file_path,
                        pending_updates={
                            each_jsonl_file_path: {
                                BYTE_OFFSET_KEY: byte_offset_after,
                                LINE_NUMBER_KEY: attachment_iterator.final_line_number,
                            },
                        },
                    )
            if batch_buffer:
                insert_rows_batch(neon_connection, batch_buffer)
            if attachment_iterator.drained:
                _merge_and_save_offsets_under_lock(
                    state_file_path=state_file_path,
                    pending_updates={
                        each_jsonl_file_path: {
                            BYTE_OFFSET_KEY: attachment_iterator.final_byte_offset,
                            LINE_NUMBER_KEY: attachment_iterator.final_line_number,
                        },
                    },
                )
    finally:
        try:
            neon_connection.close()
        except Exception:
            pass
    return EXIT_CODE_SUCCESS


def _load_starting_offsets(
    neon_connection: object,
    state_file_path: str,
    full_rebuild: bool,
) -> dict[str, dict[str, int]]:
    with _acquire_offsets_lock(state_file_path):
        if full_rebuild:
            with neon_connection.cursor() as neon_cursor:
                neon_cursor.execute(HOOK_EVENTS_TRUNCATE_SQL)
            neon_connection.commit()
            save_offsets(state_file_path, {})
            return {}
        return load_offsets(state_file_path)


def _merge_and_save_offsets_under_lock(
    state_file_path: str,
    pending_updates: dict[str, dict[str, int]],
) -> None:
    with _acquire_offsets_lock(state_file_path):
        latest_on_disk_offsets = load_offsets(state_file_path)
        merged_offsets = _merge_offsets_taking_max(
            latest_on_disk_offsets, pending_updates
        )
        save_offsets(state_file_path, merged_offsets)


def _merge_offsets_taking_max(
    disk_offsets: dict[str, dict[str, int]],
    pending_updates: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    merged: dict[str, dict[str, int]] = dict(disk_offsets)
    for each_path, each_pending_entry in pending_updates.items():
        existing_entry = merged.get(each_path)
        if existing_entry is None:
            merged[each_path] = dict(each_pending_entry)
            continue
        merged[each_path] = {
            BYTE_OFFSET_KEY: max(
                existing_entry[BYTE_OFFSET_KEY],
                each_pending_entry[BYTE_OFFSET_KEY],
            ),
            LINE_NUMBER_KEY: max(
                existing_entry[LINE_NUMBER_KEY],
                each_pending_entry[LINE_NUMBER_KEY],
            ),
        }
    return merged


def _discover_jsonl_files(transcripts_root: str) -> list[str]:
    recursive_glob_pattern = os.path.join(transcripts_root, "**", JSONL_FILE_GLOB)
    top_level_glob_pattern = os.path.join(transcripts_root, JSONL_FILE_GLOB)
    all_discovered_paths = set(glob.glob(recursive_glob_pattern, recursive=True))
    all_discovered_paths.update(glob.glob(top_level_glob_pattern))
    return sorted(all_discovered_paths)


def run_summary() -> int:
    """Print the top-10 over-blockers summary and return exit code."""
    try:
        neon_connection = connect_to_neon()
    except Exception as connect_exception:
        if is_operational_error(connect_exception):
            _append_offline_warning_line(connect_exception)
            return EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING
        raise
    try:
        with neon_connection.cursor() as neon_cursor:
            neon_cursor.execute(TOP_BLOCKERS_LAST_24_HOURS_SQL)
            all_result_rows = neon_cursor.fetchall()
    finally:
        try:
            neon_connection.close()
        except Exception:
            pass
    if not all_result_rows:
        print(SUMMARY_NO_NEW_BLOCKS_MESSAGE)
        return EXIT_CODE_SUCCESS
    _print_summary_table(all_result_rows)
    return EXIT_CODE_SUCCESS


def _print_summary_table(all_result_rows: Sequence[tuple[object, ...]]) -> None:
    all_preview_rows: list[tuple[str, str, str, str]] = []
    for each_result_row in all_result_rows:
        (
            hook_name_string,
            hook_category_string,
            block_count_integer,
            top_command_preview,
        ) = each_result_row
        truncated_preview = (top_command_preview or EMPTY_STRING)[
            :TOP_BLOCKED_COMMAND_PREVIEW_MAX_CHARACTERS
        ]
        all_preview_rows.append(
            (
                str(hook_name_string),
                str(hook_category_string),
                str(block_count_integer),
                truncated_preview,
            ),
        )
    all_display_rows = [SUMMARY_COLUMN_HEADINGS, *all_preview_rows]
    all_column_widths = [
        max(len(each_row[each_column_index]) for each_row in all_display_rows)
        for each_column_index in range(len(SUMMARY_COLUMN_HEADINGS))
    ]
    for each_display_row in all_display_rows:
        formatted_columns = [
            each_cell.ljust(all_column_widths[each_column_index])
            for each_column_index, each_cell in enumerate(each_display_row)
        ]
        print(SUMMARY_TABLE_COLUMN_GAP.join(formatted_columns))


def run_query(named_query: str) -> int:
    """Execute a pre-baked SQL file under ``queries/`` and print results."""
    if not re.fullmatch(QUERY_NAME_PATTERN, named_query):
        print(
            f"{INVALID_QUERY_NAME_MESSAGE_PREFIX}{named_query}",
            file=sys.stderr,
        )
        return EXIT_CODE_UNKNOWN_QUERY
    queries_directory = Path(__file__).resolve().parent / QUERIES_DIRECTORY_NAME
    query_file_path = queries_directory / f"{named_query}{SQL_FILE_EXTENSION}"
    if not query_file_path.exists():
        print(f"{UNKNOWN_QUERY_MESSAGE_PREFIX}{named_query}", file=sys.stderr)
        return EXIT_CODE_UNKNOWN_QUERY
    query_text = query_file_path.read_text(encoding="utf-8")
    try:
        neon_connection = connect_to_neon()
    except Exception as connect_exception:
        if is_operational_error(connect_exception):
            _append_offline_warning_line(connect_exception)
            return EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING
        raise
    try:
        with neon_connection.cursor() as neon_cursor:
            neon_cursor.execute(query_text)
            all_result_rows = neon_cursor.fetchall()
            all_column_names = [
                each_description[0]
                for each_description in (neon_cursor.description or [])
            ]
    finally:
        try:
            neon_connection.close()
        except Exception:
            pass
    if not all_result_rows:
        print(QUERY_NO_ROWS_RETURNED_MESSAGE)
        return EXIT_CODE_SUCCESS
    print(SUMMARY_TABLE_COLUMN_GAP.join(all_column_names))
    for each_result_row in all_result_rows:
        print(
            SUMMARY_TABLE_COLUMN_GAP.join(
                str(each_cell) for each_cell in each_result_row
            )
        )
    return EXIT_CODE_SUCCESS


def main() -> int:
    """Entry point for the hook-log extractor CLI.

    Supported flags:

    * ``--summary`` prints the top blockers of the last twenty-four hours.
    * ``--query <name>`` runs a pre-baked SQL file under ``queries/``.
    * ``--full-rebuild`` truncates ``hook_events`` and re-reads every
      JSONL from byte zero.
    * ``--incremental`` is a documented no-op; it selects the default
      byte-offset resumption path that the Stop hook also uses when no
      flags are passed.
    """
    all_cli_arguments = list(sys.argv[1:])
    if FLAG_SUMMARY in all_cli_arguments:
        return run_summary()
    if FLAG_QUERY in all_cli_arguments:
        flag_index = all_cli_arguments.index(FLAG_QUERY)
        if flag_index + 1 >= len(all_cli_arguments):
            return run_query(DEFAULT_QUERY_FOR_SUMMARY)
        return run_query(all_cli_arguments[flag_index + 1])
    is_full_rebuild_requested = FLAG_FULL_REBUILD in all_cli_arguments
    is_incremental_requested = FLAG_INCREMENTAL in all_cli_arguments
    if is_incremental_requested and is_full_rebuild_requested:
        is_full_rebuild_requested = False
    return run_full_extraction(
        transcripts_root=PROJECTS_TRANSCRIPT_ROOT,
        state_file_path=OFFSET_STATE_FILE,
        full_rebuild=is_full_rebuild_requested,
    )


if __name__ == "__main__":
    sys.exit(main())
