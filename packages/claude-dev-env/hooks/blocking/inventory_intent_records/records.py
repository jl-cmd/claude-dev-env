"""Shared pending-intent notes that break the inventory/orphan write deadlock.

::

    write foo/bar.py        -> inventory deny, records FILE intent(foo, bar.py)
    add row for bar.py      -> orphan reads the FILE intent, allows the row
    retry write foo/bar.py  -> inventory reads the row on disk, allows the file

Each blocker writes a note when it denies and reads the sibling's note to allow
the matching second write. A note pairs a directory with a filename and its
record time; a note past the freshness window is ignored, and a consumed note is
removed so it opens the gate once. Both blockers share one JSON file per session
under the temp directory, and a missing or corrupt file reads as no notes.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from inventory_intent_records.config.intent_records_constants import (
    ALL_FILE_INTENTS_KEY,
    ALL_ROW_INTENTS_KEY,
    INTENT_DIRECTORY_FIELD,
    INTENT_FILE_PREFIX,
    INTENT_FILE_SUFFIX,
    INTENT_FILENAME_FIELD,
    INTENT_FRESHNESS_WINDOW_SECONDS,
    INTENT_RECORDED_AT_FIELD,
)

from hooks_constants.session_edit_stage_gate_constants import (
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
    STATE_FILE_ATOMIC_WRITE_SUFFIX,
    STATE_FILE_DEFAULT_SESSION_ID,
    STATE_FILE_JSON_INDENT_SPACES,
)


def _intent_file_path(session_id: str) -> Path:
    """Return this session's shared intent-records file in the temp directory.

    Args:
        session_id: Raw session id; unsafe characters are stripped and an empty
            result falls back to the default id.

    Returns:
        The absolute path of this session's intent-records file.
    """
    sanitized_session_id = SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)
    effective_session_id = sanitized_session_id or STATE_FILE_DEFAULT_SESSION_ID
    file_name = f"{INTENT_FILE_PREFIX}{effective_session_id}{INTENT_FILE_SUFFIX}"
    return Path(tempfile.gettempdir()) / file_name


def _empty_records() -> dict[str, list[dict[str, object]]]:
    """Return an empty two-list records structure."""
    return {ALL_FILE_INTENTS_KEY: [], ALL_ROW_INTENTS_KEY: []}


def _intent_list(all_records: dict[str, object], intents_key: str) -> list[dict[str, object]]:
    """Return the well-formed intent dictionaries stored under one list key.

    Args:
        all_records: A parsed records payload.
        intents_key: The file-intents or row-intents list key.

    Returns:
        Each dictionary entry under the key; a malformed value yields an empty list.
    """
    stored_value = all_records.get(intents_key, [])
    if not isinstance(stored_value, list):
        return []
    return [each_entry for each_entry in stored_value if isinstance(each_entry, dict)]


def _read_records(session_id: str) -> dict[str, list[dict[str, object]]]:
    """Return this session's records, or an empty structure when unreadable.

    Args:
        session_id: Raw session id keying the shared records file.

    Returns:
        The two-list records structure; a missing, malformed, or wrong-shape
        file reads as an empty structure so a storage fault falls back to no notes.
    """
    intent_file = _intent_file_path(session_id)
    try:
        raw_text = intent_file.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return _empty_records()
    try:
        parsed_payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return _empty_records()
    if not isinstance(parsed_payload, dict):
        return _empty_records()
    return {
        ALL_FILE_INTENTS_KEY: _intent_list(parsed_payload, ALL_FILE_INTENTS_KEY),
        ALL_ROW_INTENTS_KEY: _intent_list(parsed_payload, ALL_ROW_INTENTS_KEY),
    }


def _write_records(session_id: str, all_records: dict[str, list[dict[str, object]]]) -> None:
    """Write the records structure atomically, failing open on an OS error.

    Args:
        session_id: Raw session id keying the shared records file.
        all_records: The full records structure to persist.
    """
    intent_file = _intent_file_path(session_id)
    temporary_file = intent_file.with_name(intent_file.name + STATE_FILE_ATOMIC_WRITE_SUFFIX)
    encoded_text = json.dumps(all_records, indent=STATE_FILE_JSON_INDENT_SPACES)
    try:
        temporary_file.write_text(encoded_text, encoding="utf-8")
        os.replace(str(temporary_file), str(intent_file))
    except OSError:
        return


def _is_fresh(intent_record: dict, current_time: float) -> bool:
    """Return whether one intent was recorded within the freshness window.

    Args:
        intent_record: One stored intent dictionary.
        current_time: The current epoch time.

    Returns:
        True when the record time is present and within the window.
    """
    recorded_at = intent_record.get(INTENT_RECORDED_AT_FIELD)
    if not isinstance(recorded_at, (int, float)):
        return False
    return current_time - float(recorded_at) <= INTENT_FRESHNESS_WINDOW_SECONDS


def _matches_target(intent_record: dict, directory: str, filename: str) -> bool:
    """Return whether one intent names the given directory and filename.

    Args:
        intent_record: One stored intent dictionary.
        directory: The resolved directory to match.
        filename: The bare filename to match.

    Returns:
        True when both the directory and filename fields equal the target.
    """
    return (
        intent_record.get(INTENT_DIRECTORY_FIELD) == directory
        and intent_record.get(INTENT_FILENAME_FIELD) == filename
    )


def _record_intent(session_id: str, intents_key: str, directory: str, filename: str) -> None:
    """Add one pending intent, dropping stale notes and any prior same-target note."""
    all_records = _read_records(session_id)
    current_time = time.time()
    kept_intents = [
        each_intent
        for each_intent in all_records[intents_key]
        if _is_fresh(each_intent, current_time)
        and not _matches_target(each_intent, directory, filename)
    ]
    kept_intents.append(
        {
            INTENT_DIRECTORY_FIELD: directory,
            INTENT_FILENAME_FIELD: filename,
            INTENT_RECORDED_AT_FIELD: current_time,
        }
    )
    all_records[intents_key] = kept_intents
    _write_records(session_id, all_records)


def _has_fresh_intent(session_id: str, intents_key: str, directory: str, filename: str) -> bool:
    """Return whether a fresh pending intent names the directory and filename."""
    all_records = _read_records(session_id)
    current_time = time.time()
    return any(
        _is_fresh(each_intent, current_time) and _matches_target(each_intent, directory, filename)
        for each_intent in all_records[intents_key]
    )


def _consume_intent(session_id: str, intents_key: str, directory: str, filename: str) -> None:
    """Remove every pending intent naming the directory and filename."""
    all_records = _read_records(session_id)
    current_time = time.time()
    remaining_intents = [
        each_intent
        for each_intent in all_records[intents_key]
        if _is_fresh(each_intent, current_time)
        and not _matches_target(each_intent, directory, filename)
    ]
    all_records[intents_key] = remaining_intents
    _write_records(session_id, all_records)


def record_file_intent(session_id: str, directory: str, filename: str) -> None:
    """Record that a new file write was denied for want of its inventory row.

    Args:
        session_id: Raw session id keying the shared records file.
        directory: The resolved directory the new file lands in.
        filename: The bare filename of the denied new file.
    """
    _record_intent(session_id, ALL_FILE_INTENTS_KEY, directory, filename)


def record_row_intent(session_id: str, directory: str, filename: str) -> None:
    """Record that an inventory row was denied for want of the file it names.

    Args:
        session_id: Raw session id keying the shared records file.
        directory: The resolved directory of the inventory document.
        filename: The bare filename the denied row names.
    """
    _record_intent(session_id, ALL_ROW_INTENTS_KEY, directory, filename)


def has_fresh_file_intent(session_id: str, directory: str, filename: str) -> bool:
    """Return whether a fresh file intent names the directory and filename.

    Args:
        session_id: Raw session id keying the shared records file.
        directory: The resolved directory to match.
        filename: The bare filename to match.

    Returns:
        True when a matching fresh file intent exists.
    """
    return _has_fresh_intent(session_id, ALL_FILE_INTENTS_KEY, directory, filename)


def has_fresh_row_intent(session_id: str, directory: str, filename: str) -> bool:
    """Return whether a fresh row intent names the directory and filename.

    Args:
        session_id: Raw session id keying the shared records file.
        directory: The resolved directory to match.
        filename: The bare filename to match.

    Returns:
        True when a matching fresh row intent exists.
    """
    return _has_fresh_intent(session_id, ALL_ROW_INTENTS_KEY, directory, filename)


def consume_file_intent(session_id: str, directory: str, filename: str) -> None:
    """Remove the file intent naming the directory and filename.

    Args:
        session_id: Raw session id keying the shared records file.
        directory: The resolved directory of the consumed file intent.
        filename: The bare filename of the consumed file intent.
    """
    _consume_intent(session_id, ALL_FILE_INTENTS_KEY, directory, filename)


def consume_row_intent(session_id: str, directory: str, filename: str) -> None:
    """Remove the row intent naming the directory and filename.

    Args:
        session_id: Raw session id keying the shared records file.
        directory: The resolved directory of the consumed row intent.
        filename: The bare filename of the consumed row intent.
    """
    _consume_intent(session_id, ALL_ROW_INTENTS_KEY, directory, filename)
