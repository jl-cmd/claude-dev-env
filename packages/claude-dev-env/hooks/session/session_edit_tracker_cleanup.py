#!/usr/bin/env python3
"""SessionStart hook: clear this session's tracker file and prune stale ones.

The session-edit tracker writes a per-session JSON file under the system temp
directory, and the stage gate reads it at commit time. A session that crashes
or is interrupted leaves its tracker file behind, and a fresh session should
start with an empty record. At session start this hook deletes the current
session's own tracker file and prunes any tracker file older than the stale-age
threshold, so the temp directory does not fill with abandoned records.

The hook exits zero on every branch and never blocks the session.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    SESSION_EDIT_FILE_PREFIX,
    SESSION_EDIT_FILE_STALE_AGE_SECONDS,
    SESSION_EDIT_FILE_SUFFIX,
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
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


def _delete_current_session_file(temp_directory: Path, session_id: str) -> None:
    """Delete the tracker file that belongs to the current session.

    Args:
        temp_directory: System temp directory holding the tracker files.
        session_id: Raw ``session_id`` from the SessionStart payload.
    """
    sanitized_session_id = SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)
    effective_session_id = sanitized_session_id or STATE_FILE_DEFAULT_SESSION_ID
    file_name = f"{SESSION_EDIT_FILE_PREFIX}{effective_session_id}{SESSION_EDIT_FILE_SUFFIX}"
    _delete_file(temp_directory / file_name)


def _prune_stale_files(temp_directory: Path) -> None:
    """Delete every tracker file older than the stale-age threshold.

    Args:
        temp_directory: System temp directory holding the tracker files.
    """
    glob_pattern = f"{SESSION_EDIT_FILE_PREFIX}*{SESSION_EDIT_FILE_SUFFIX}"
    current_time_seconds = time.time()
    try:
        all_candidate_paths = list(temp_directory.glob(glob_pattern))
    except OSError:
        return
    for each_candidate_path in all_candidate_paths:
        try:
            modified_time_seconds = each_candidate_path.stat().st_mtime
        except OSError:
            continue
        if current_time_seconds - modified_time_seconds >= SESSION_EDIT_FILE_STALE_AGE_SECONDS:
            _delete_file(each_candidate_path)


def main() -> None:
    """Delete this session's tracker file and prune stale tracker files.

    Reads the SessionStart payload from stdin for the session id, deletes the
    current session's tracker file, and prunes every tracker file past the
    stale-age threshold. Exits zero on every branch, including a malformed or
    empty payload, so the session is never blocked.
    """
    hook_payload = read_hook_input_dictionary_from_stdin()
    session_id = str(hook_payload.get("session_id") or "") if hook_payload else ""
    temp_directory = Path(tempfile.gettempdir())
    _delete_current_session_file(temp_directory, session_id)
    _prune_stale_files(temp_directory)


if __name__ == "__main__":
    main()
