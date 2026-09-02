#!/usr/bin/env python3
"""PostToolUse hook: record that this session spawned the pr-description-writer agent.

Picture opening a pull request whose body nobody wrote from the diff — it reads
like a commit message, and the reviewer learns nothing before opening the files.
The ``pr-description-writer`` agent exists to write that body, and it hands the
markdown and a body-file path back to the caller to publish.

This hook remembers that the agent ran. After each Agent or Task spawn naming
``pr-description-writer``, it touches an empty marker file for this session in
the system temp directory. The ``gh pr create`` gate reads that marker.

The marker carries one fact — the agent ran this session — so a touch records
everything the gate needs, and two parallel spawns racing on the same touch
leave the same result. The file name carries the session id, so a marker a
crashed session leaves behind is inert: no later session reads it.

The hook never blocks a tool call. A tool that is not a spawn, a spawn of
another agent, a malformed payload, a payload naming no session, or a failed
touch each returns quietly.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.pr_description_writer_gate_constants import (  # noqa: E402
    ALL_AGENT_SPAWN_TOOL_NAMES,
    PR_DESCRIPTION_WRITER_SUBAGENT_TYPE,
    SPAWN_MARKER_FILE_PREFIX,
    SPAWN_MARKER_FILE_SUFFIX,
    SUBAGENT_TYPE_FIELD_NAME,
    TOOL_INPUT_FIELD_NAME,
    TOOL_NAME_FIELD_NAME,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
)


def spawn_marker_path(session_id: str, temp_directory: Path | None = None) -> Path | None:
    """Return the marker path for one session, or None without a usable id.

    ::

        session_id = "abc-123"  ->  <temp>/claude-session-pr-description-writer-abc-123.marker
        session_id = ""         ->  None
        session_id = "///"      ->  None

    Unsafe characters are stripped so the name stays anchored inside the temp
    directory. A session id that sanitizes to nothing yields no path, so every
    marker on disk belongs to one real session and a marker a crashed session
    leaves behind is inert — no later session reads it.

    Args:
        session_id: Raw ``session_id`` from the hook payload.
        temp_directory: The directory holding the marker. Defaults to the
            system temp directory.

    Returns:
        Absolute path to this session's marker file, or None when the payload
        names no session this hook can key on.
    """
    sanitized_session_id = SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)
    if not sanitized_session_id:
        return None
    file_name = f"{SPAWN_MARKER_FILE_PREFIX}{sanitized_session_id}{SPAWN_MARKER_FILE_SUFFIX}"
    resolved_temp_directory = temp_directory or Path(tempfile.gettempdir())
    return resolved_temp_directory / file_name


def _record_spawn(session_id: str) -> None:
    """Touch this session's marker file, ignoring a write failure.

    Args:
        session_id: Raw ``session_id`` from the hook payload.
    """
    marker_file = spawn_marker_path(session_id)
    if marker_file is None:
        return
    try:
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        marker_file.touch(exist_ok=True)
    except OSError:
        return


def main() -> None:
    """Record the marker when this payload is a pr-description-writer spawn.

    Reads the PostToolUse payload from stdin and touches this session's marker
    file when an Agent or Task spawn names the ``pr-description-writer`` agent.
    Returns on every other branch — another tool, another agent, a malformed
    payload, or a missing ``tool_input`` — so the spawn is never blocked.
    """
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        return
    tool_name = hook_payload.get(TOOL_NAME_FIELD_NAME, "")
    if tool_name not in ALL_AGENT_SPAWN_TOOL_NAMES:
        return
    tool_input = hook_payload.get(TOOL_INPUT_FIELD_NAME, {})
    if not isinstance(tool_input, dict):
        return
    if tool_input.get(SUBAGENT_TYPE_FIELD_NAME) != PR_DESCRIPTION_WRITER_SUBAGENT_TYPE:
        return
    session_id = str(hook_payload.get("session_id") or "")
    _record_spawn(session_id)


if __name__ == "__main__":
    main()
