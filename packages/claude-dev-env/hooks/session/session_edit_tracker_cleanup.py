#!/usr/bin/env python3
"""SessionStart and SessionEnd hook: clear this session's own tracker file.

The session-edit tracker writes a per-session JSON file under the system temp
directory, and the stage gate reads only the running session's own file at
commit time. This hook deletes that file only when the session is genuinely
beginning or ending: at a fresh SessionStart (a ``startup`` source) so a new
session begins with an empty record, and at session end so a clean exit leaves
nothing behind. A SessionStart that continues the same conversation — a compact
or a resume — keeps the in-flight tracker, so an edit already recorded this
session survives the continuation.

A tracker file belongs to one session and is read only by that same session, so
a file a hard-crashed session leaves behind is inert — no other session ever
reads it. Cleanup keys off the session lifecycle rather than a file's age, so a
live session that pauses for a long review gap keeps its own tracker: no peer
session deletes another session's file.

The hook exits zero on every branch and never blocks the session.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    SESSION_EDIT_FILE_PREFIX,
    SESSION_EDIT_FILE_SUFFIX,
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
    SESSION_START_SOURCE_FRESH_STARTUP,
    SESSION_START_SOURCE_PAYLOAD_KEY,
    STATE_FILE_DEFAULT_SESSION_ID,
)


def _delete_file(target_file: Path) -> None:
    """Remove a file, ignoring an already-absent file or a delete failure.

    Args:
        target_file: Path to delete.
    """
    try:
        target_file.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _current_session_file_name(session_id: str) -> str:
    """Return the tracker file name that belongs to the current session.

    Args:
        session_id: Raw ``session_id`` from the session-lifecycle payload.

    Returns:
        The tracker file name for the sanitized session id, falling back to
        the default id when sanitizing leaves an empty string.
    """
    sanitized_session_id = SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)
    effective_session_id = sanitized_session_id or STATE_FILE_DEFAULT_SESSION_ID
    return f"{SESSION_EDIT_FILE_PREFIX}{effective_session_id}{SESSION_EDIT_FILE_SUFFIX}"


def _is_tracker_deletion_lifecycle_event(payload_by_field: dict[str, object]) -> bool:
    """Report whether this lifecycle event should delete the session tracker.

    The ``source`` key rides only on a SessionStart payload. A fresh startup
    carries the ``startup`` source and a session end carries no source at all,
    so both delete the tracker. A SessionStart that continues the same
    conversation carries a non-startup source (a compact or a resume) and keeps
    the in-flight tracker.

    Args:
        payload_by_field: The parsed session-lifecycle payload.

    Returns:
        True when the tracker should be deleted, False when a continuation
        should keep it.
    """
    session_start_source = str(
        payload_by_field.get(SESSION_START_SOURCE_PAYLOAD_KEY) or ""
    )
    if not session_start_source:
        return True
    return session_start_source == SESSION_START_SOURCE_FRESH_STARTUP


def main() -> None:
    """Delete the running session's own tracker file at a fresh start or end.

    Reads the session-lifecycle payload from stdin for the session id and
    deletes that session's tracker file from the system temp directory, unless
    the payload is a SessionStart that continues the same conversation (a
    compact or a resume), which keeps the in-flight tracker. Exits zero on
    every branch, including a malformed or empty payload, so the session is
    never blocked.
    """
    payload_by_field = read_hook_input_dictionary_from_stdin() or {}
    if not _is_tracker_deletion_lifecycle_event(payload_by_field):
        return
    session_id = str(payload_by_field.get("session_id") or "")
    temp_directory = Path(tempfile.gettempdir())
    current_session_file_name = _current_session_file_name(session_id)
    _delete_file(temp_directory / current_session_file_name)


if __name__ == "__main__":
    main()
