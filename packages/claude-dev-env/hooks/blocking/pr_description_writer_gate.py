#!/usr/bin/env python3
"""PreToolUse hook: block gh pr create when no pr-description-writer spawn is recorded.

Picture a reviewer opening a fresh pull request and meeting a body that repeats
the branch name. The ``pr-description-writer`` agent exists to write that body
from the diff, and the spawn tracker records each time this session runs it.

This gate reads that record when the session runs ``gh pr create``::

    gh pr create --body-file body.md            flag: no spawn recorded
    gh pr create --body-file body.md            ok:   a spawn recorded earlier
    gh pr create ... # pr-description-skip      ok:   the author opted out

Detection strategy: tokenize the command, then check each position that opens a
command segment for a ``gh`` executable followed by ``pr`` and ``create``. The
bypass marker counts only as the command's final tokens, so the same text
inside a quoted title leaves the gate running.

The gate fails OPEN on anything it cannot read: a command that will not
tokenize, a payload that is not a shell tool, or a missing command. Only a
recognized ``gh pr create`` with no recorded spawn and no bypass marker denies.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

_blocking_dir = str(Path(__file__).resolve().parent)
if _blocking_dir not in sys.path:
    sys.path.insert(0, _blocking_dir)

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (  # noqa: E402
    ALL_BASH_AND_POWERSHELL_TOOL_NAMES,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.pr_description_writer_gate_constants import (  # noqa: E402
    ALL_GH_EXECUTABLE_BASENAMES,
    COMMAND_FIELD_NAME,
    CORRECTIVE_MESSAGE,
    CREATE_SUBCOMMAND_TOKEN,
    GH_PR_CREATE_MINIMUM_TOKEN_COUNT,
    PR_SUBCOMMAND_TOKEN,
    SPAWN_BYPASS_MARKER,
    TOOL_INPUT_FIELD_NAME,
    TOOL_NAME_FIELD_NAME,
    spawn_marker_path,
)
from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    ALL_COMMAND_SEPARATOR_TOKENS,
)
from sensitive_file_protector import build_deny_response  # noqa: E402


def _all_command_tokens(shell_command: str) -> list[str] | None:
    """Return the command's tokens, or None when it will not tokenize.

    Args:
        shell_command: The raw shell command string.

    Returns:
        The token list, or None when shlex rejects the command.
    """
    try:
        return shlex.split(shell_command, posix=True)
    except ValueError:
        return None


def _carries_trailing_bypass_marker(all_tokens: list[str]) -> bool:
    """Report whether the bypass marker sits at the very end of the command.

    The marker opts out only as a trailing shell comment the author adds on
    purpose, so its parts are the command's final tokens. The same text inside
    a quoted title tokenizes into the middle of the list and does not match.

    Args:
        all_tokens: The tokens of the whole command.

    Returns:
        True when the marker's tokens close the command.
    """
    all_marker_tokens = SPAWN_BYPASS_MARKER.split()
    marker_length = len(all_marker_tokens)
    if marker_length > len(all_tokens):
        return False
    return all_tokens[-marker_length:] == all_marker_tokens


def _opens_pull_request_creation(all_leading_tokens: list[str]) -> bool:
    """Report whether these leading tokens open a gh pr create invocation.

    Args:
        all_leading_tokens: The tokens that open one command segment.

    Returns:
        True when they name a gh executable, then ``pr``, then ``create``.
    """
    if len(all_leading_tokens) < GH_PR_CREATE_MINIMUM_TOKEN_COUNT:
        return False
    executable_basename = Path(all_leading_tokens[0]).name
    if executable_basename not in ALL_GH_EXECUTABLE_BASENAMES:
        return False
    return all_leading_tokens[1:] == [PR_SUBCOMMAND_TOKEN, CREATE_SUBCOMMAND_TOKEN]


def _all_command_segments(all_tokens: list[str]) -> list[list[str]]:
    """Return the command's token segments in their original order.

    A shell separator ends the current segment and starts the next one.

    Args:
        all_tokens: The tokens of the whole command.

    Returns:
        One token list for each command segment.
    """
    all_segments: list[list[str]] = [[]]
    for each_token in all_tokens:
        if each_token in ALL_COMMAND_SEPARATOR_TOKENS:
            all_segments.append([])
            continue
        all_segments[-1].append(each_token)
    return all_segments


def _all_pull_request_creation_segment_indexes(all_segments: list[list[str]]) -> list[int]:
    """Return indexes for segments that open a gh pr create command.

    Args:
        all_segments: The shell command's token segments.

    Returns:
        The indexes of segments that open a gh pr create command.
    """
    return [
        each_index
        for each_index, each_segment in enumerate(all_segments)
        if _opens_pull_request_creation(each_segment[:GH_PR_CREATE_MINIMUM_TOKEN_COUNT])
    ]


def _only_final_create_carries_bypass(
    all_tokens: list[str],
    all_segments: list[list[str]],
    all_creation_segment_indexes: list[int],
) -> bool:
    """Report whether one final gh pr create carries the final bypass comment.

    The marker belongs to the command segment that creates the pull request.
    A marker after another command, or after a second create, cannot opt an
    earlier create out.

    Args:
        all_tokens: The tokens of the whole command.
        all_segments: The command's token segments, already split by the caller.
        all_creation_segment_indexes: Indexes of segments that create pull requests.

    Returns:
        True when one final create segment carries the final bypass marker.
    """
    if not _carries_trailing_bypass_marker(all_tokens):
        return False
    final_segment_index = len(all_segments) - 1
    return all_creation_segment_indexes == [final_segment_index]


def _spawn_is_recorded(session_id: str) -> bool:
    """Report whether this session recorded a pr-description-writer spawn.

    A payload naming no session reads as no record, so the gate denies rather
    than falling back to a shared marker a different session could have left.

    Args:
        session_id: Raw ``session_id`` from the hook payload.

    Returns:
        True when this session's marker file is present.
    """
    marker_file = spawn_marker_path(session_id)
    return marker_file is not None and marker_file.exists()


def _shell_command_or_none(all_hook_payload: dict[str, object]) -> str | None:
    """Return the shell command this payload carries, or None.

    Args:
        all_hook_payload: The parsed PreToolUse payload.

    Returns:
        The command string, or None when the payload runs no shell command.
    """
    if all_hook_payload.get(TOOL_NAME_FIELD_NAME, "") not in ALL_BASH_AND_POWERSHELL_TOOL_NAMES:
        return None
    tool_input = all_hook_payload.get(TOOL_INPUT_FIELD_NAME, {})
    if not isinstance(tool_input, dict):
        return None
    shell_command = tool_input.get(COMMAND_FIELD_NAME, "")
    if not isinstance(shell_command, str) or not shell_command:
        return None
    return shell_command


def _emit_denial() -> None:
    """Write the PreToolUse deny payload to stdout and log the block."""
    log_hook_block(
        calling_hook_name="pr_description_writer_gate.py",
        hook_event="PreToolUse",
        block_reason=CORRECTIVE_MESSAGE,
    )
    sys.stdout.write(json.dumps(build_deny_response(CORRECTIVE_MESSAGE)) + "\n")
    sys.stdout.flush()


def main() -> None:
    """Deny a gh pr create that no recorded agent spawn or bypass marker covers.

    Reads the PreToolUse payload from stdin and exits zero on every branch. A
    tool that runs no shell, a missing command, a command that will not
    tokenize, a command opening no pull request, a trailing bypass marker, and
    a recorded spawn each pass through untouched.
    """
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        sys.exit(0)
    shell_command = _shell_command_or_none(hook_payload)
    if shell_command is None:
        sys.exit(0)
    all_tokens = _all_command_tokens(shell_command)
    if all_tokens is None:
        sys.exit(0)
    all_segments = _all_command_segments(all_tokens)
    all_creation_segment_indexes = _all_pull_request_creation_segment_indexes(all_segments)
    if not all_creation_segment_indexes:
        sys.exit(0)
    if _only_final_create_carries_bypass(
        all_tokens, all_segments, all_creation_segment_indexes
    ):
        sys.exit(0)
    if _spawn_is_recorded(str(hook_payload.get("session_id") or "")):
        sys.exit(0)
    _emit_denial()
    sys.exit(0)


if __name__ == "__main__":
    main()
