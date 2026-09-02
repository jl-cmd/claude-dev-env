"""Constants for the pr-description-writer spawn tracker and its gh pr create gate.

The tracker records one fact per session: the session spawned the
``pr-description-writer`` agent. The gate reads that fact when the session runs
``gh pr create`` and denies the command when the fact is absent.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hooks_constants.session_edit_stage_gate_constants import (
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
)

PR_DESCRIPTION_WRITER_SUBAGENT_TYPE: str = "pr-description-writer"

ALL_AGENT_SPAWN_TOOL_NAMES: frozenset[str] = frozenset({"Agent", "Task"})

SPAWN_MARKER_FILE_PREFIX: str = "claude-session-pr-description-writer-"
SPAWN_MARKER_FILE_SUFFIX: str = ".marker"

SUBAGENT_TYPE_FIELD_NAME: str = "subagent_type"
TOOL_INPUT_FIELD_NAME: str = "tool_input"
TOOL_NAME_FIELD_NAME: str = "tool_name"
COMMAND_FIELD_NAME: str = "command"

ALL_GH_EXECUTABLE_BASENAMES: frozenset[str] = frozenset({"gh", "gh.exe", "gh.cmd"})
PR_SUBCOMMAND_TOKEN: str = "pr"
CREATE_SUBCOMMAND_TOKEN: str = "create"
GH_PR_CREATE_MINIMUM_TOKEN_COUNT: int = 3

SPAWN_BYPASS_MARKER: str = "# pr-description-skip"

CORRECTIVE_MESSAGE: str = (
    "BLOCKED: [PR_DESCRIPTION_WRITER] This session runs `gh pr create` with no "
    "`pr-description-writer` agent spawn recorded.\n\n"
    "The agent writes the title and body from the current diff, then returns the "
    "markdown and a body-file path for you to publish.\n\n"
    "Two ways forward:\n"
    "  1. Spawn the agent (Agent tool, subagent_type `pr-description-writer`), "
    "then run `gh pr create --body-file <path>` with what it returns.\n"
    "  2. Append the trailing comment `# pr-description-skip` to the command when "
    "you are writing the body yourself on purpose."
)


def spawn_marker_path(session_id: str, temp_directory: Path | None = None) -> Path | None:
    """Return this session's marker file path, or None when it names no session.

    The tracker writes this path and the gate reads it, so the file name lives
    in one place. A session id that sanitizes to nothing yields no path, so
    every marker on disk belongs to one real session and a marker a crashed
    session leaves behind is inert.

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
    file_name = (
        f"{SPAWN_MARKER_FILE_PREFIX}{sanitized_session_id}{SPAWN_MARKER_FILE_SUFFIX}"
    )
    resolved_temp_directory = temp_directory or Path(tempfile.gettempdir())
    return resolved_temp_directory / file_name
