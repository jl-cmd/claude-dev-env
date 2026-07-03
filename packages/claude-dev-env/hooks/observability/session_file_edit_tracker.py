#!/usr/bin/env python3
"""PostToolUse hook: record files edited this session for the stage gate.

Picture finishing a change, running `git commit`, and later finding one file
never made it in — it was edited but never staged, and the commit dropped it
silently. This hook prevents that by remembering every file the session
touches. After each Write, Edit, or MultiEdit it appends the edited file's
resolved absolute path to a per-session JSON file in the system temp directory,
which the stage gate reads at commit time. Concurrent invocations — the case
parallel Write or Edit calls in one turn produce — serialize on a best-effort
per-session lock file. When the lock cannot be acquired within the timeout, the
write proceeds without it rather than stalling the edit that triggered the hook.

The hook never blocks a tool call. A non-edit tool, a malformed payload, a
missing file path, or a failed write each returns quietly, so a logging problem
never interrupts the edit that triggered it.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    ALL_EDITED_FILE_PATHS_KEY,
    ALL_TRACKED_EDIT_TOOL_NAMES,
    LOCK_ACQUIRE_RETRY_SECONDS,
    LOCK_ACQUIRE_TIMEOUT_SECONDS,
    SESSION_EDIT_FILE_PREFIX,
    SESSION_EDIT_FILE_SUFFIX,
    SESSION_EDIT_LOCK_FILE_SUFFIX,
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
    STATE_FILE_ATOMIC_WRITE_SUFFIX,
    STATE_FILE_DEFAULT_SESSION_ID,
    STATE_FILE_JSON_INDENT_SPACES,
)


def _session_edit_file_path(session_id: str) -> Path:
    """Return the per-session tracker file path in the system temp directory.

    Args:
        session_id: Raw ``session_id`` from the hook payload. Unsafe
            characters are stripped so the value stays anchored inside the
            temp directory, and an empty result falls back to the default id.

    Returns:
        Absolute path to this session's tracker file.
    """
    sanitized_session_id = SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)
    effective_session_id = sanitized_session_id or STATE_FILE_DEFAULT_SESSION_ID
    file_name = f"{SESSION_EDIT_FILE_PREFIX}{effective_session_id}{SESSION_EDIT_FILE_SUFFIX}"
    return Path(tempfile.gettempdir()) / file_name


def _read_recorded_paths(edit_file: Path) -> list[str]:
    """Return the file paths already recorded in a tracker file.

    Args:
        edit_file: Path to this session's tracker file.

    Returns:
        The recorded absolute paths, or an empty list when the file is
        absent, unreadable, malformed, or the wrong shape.
    """
    try:
        raw_contents = edit_file.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return []
    try:
        parsed_payload = json.loads(raw_contents)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed_payload, dict):
        return []
    recorded_paths = parsed_payload.get(ALL_EDITED_FILE_PATHS_KEY, [])
    if not isinstance(recorded_paths, list):
        return []
    return [each_path for each_path in recorded_paths if isinstance(each_path, str)]


def _atomic_write_edit_file(edit_file: Path, all_edited_file_paths: list[str]) -> None:
    """Write the tracker payload to disk atomically via tempfile plus rename.

    Args:
        edit_file: Destination tracker file path.
        all_edited_file_paths: The full deduplicated path list to persist.
    """
    parent_directory = edit_file.parent
    parent_directory.mkdir(parents=True, exist_ok=True)
    encoded_text = json.dumps(
        {ALL_EDITED_FILE_PATHS_KEY: all_edited_file_paths},
        indent=STATE_FILE_JSON_INDENT_SPACES,
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(parent_directory),
        delete=False,
        suffix=STATE_FILE_ATOMIC_WRITE_SUFFIX,
    ) as temporary_handle:
        temporary_handle.write(encoded_text)
        temporary_path = Path(temporary_handle.name)
    try:
        os.replace(str(temporary_path), str(edit_file))
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise


def _acquire_edit_file_lock(lock_file: Path) -> int | None:
    """Grab an exclusive per-session lock, spinning until it frees or times out.

    Args:
        lock_file: Path to this session's lock file.

    Returns:
        An open file descriptor for the held lock, or None when the lock stayed
        held past the acquire timeout so the caller proceeds without it rather
        than stalling the edit that triggered the hook.
    """
    lock_acquire_deadline = time.monotonic() + LOCK_ACQUIRE_TIMEOUT_SECONDS
    while True:
        try:
            return os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= lock_acquire_deadline:
                return None
            time.sleep(LOCK_ACQUIRE_RETRY_SECONDS)


@contextlib.contextmanager
def _hold_edit_file_lock(edit_file: Path) -> Iterator[None]:
    """Hold the per-session lock across one read-modify-write of the tracker.

    Two PostToolUse invocations run concurrently when Claude issues parallel
    Write or Edit calls in one turn. Serializing the read-then-write on a shared
    lock file keeps each invocation's appended path from overwriting another's.
    The lock is best-effort: when it cannot be acquired within the timeout, the
    write proceeds without it rather than stalling the edit.

    Args:
        edit_file: This session's tracker file path.

    Yields:
        Control to the caller while the lock is held.
    """
    lock_file = edit_file.with_name(edit_file.name + SESSION_EDIT_LOCK_FILE_SUFFIX)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_descriptor = _acquire_edit_file_lock(lock_file)
    try:
        yield
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
            lock_file.unlink(missing_ok=True)


def _record_edited_path(session_id: str, resolved_file_path: str) -> None:
    """Append one edited path to this session's tracker file when it is new.

    The read of the recorded paths and the write back run under a best-effort
    per-session lock, so parallel invocations do not drop one another's appended
    path while the lock holds.

    Args:
        session_id: Raw ``session_id`` from the hook payload.
        resolved_file_path: The resolved absolute path of the edited file.
    """
    edit_file = _session_edit_file_path(session_id)
    with _hold_edit_file_lock(edit_file):
        recorded_paths = _read_recorded_paths(edit_file)
        if resolved_file_path in recorded_paths:
            return
        recorded_paths.append(resolved_file_path)
        try:
            _atomic_write_edit_file(edit_file, recorded_paths)
        except OSError:
            return


def main() -> None:
    """Record the edited file path for a Write, Edit, or MultiEdit.

    Reads the PostToolUse payload from stdin, and for a tracked edit tool
    appends the resolved absolute file path to this session's tracker file.
    Returns on every branch — a non-edit tool, a malformed payload, a missing
    file path, or a failed write — so the tool call is never blocked.
    """
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        return
    tool_name = hook_payload.get("tool_name", "")
    if tool_name not in ALL_TRACKED_EDIT_TOOL_NAMES:
        return
    tool_input = hook_payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return
    try:
        resolved_file_path = str(Path(file_path).resolve())
    except OSError:
        return
    session_id = str(hook_payload.get("session_id") or "")
    _record_edited_path(session_id, resolved_file_path)


if __name__ == "__main__":
    main()
