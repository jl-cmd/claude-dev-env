#!/usr/bin/env python3
"""PreToolUse hook: remind the agent to update the issue tracker on commit or push.

On a Bash ``git commit`` or ``git push`` this hook returns an allow decision
carrying additionalContext that tells the agent to refresh tracked issues, check
off finished children, and give a finished sub-issue a ``Closes #N`` line. On any
other command the hook stays silent, so it never changes a non-git call. It runs
hosted inside the Bash PreToolUse dispatcher — where it is the last roster entry,
so a deny gate short-circuits ahead of this allow-only reminder — and imports its
constants through the hooks directory the dispatcher places on ``sys.path``.
"""

from __future__ import annotations

import json
import shlex
import sys

from hooks_constants.issue_tracker_commit_reminder_constants import (
    ADDITIONAL_CONTEXT_KEY,
    ALL_ARGUMENT_TAKING_GLOBAL_FLAGS,
    ALL_COMMAND_SEPARATOR_TOKENS,
    ALL_GIT_EXECUTABLE_TOKENS,
    ALL_REMINDER_TRIGGER_SUBCOMMANDS,
    ALLOW_PERMISSION_DECISION,
    COMMAND_INPUT_KEY,
    FLAG_TOKEN_PREFIX,
    FLAG_WITH_VALUE_TOKEN_SPAN,
    HOOK_EVENT_NAME_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    ISSUE_TRACKER_COMMIT_REMINDER_TEXT,
    PERMISSION_DECISION_KEY,
    POSIX_PATH_SEPARATOR,
    PRE_TOOL_USE_EVENT_NAME,
    TOOL_INPUT_PAYLOAD_KEY,
    WINDOWS_PATH_SEPARATOR,
)
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin


def _tokenize_command(command_text: str) -> list[str]:
    """Split a shell command into tokens, falling back to whitespace on a parse error."""
    try:
        return shlex.split(command_text, posix=True)
    except ValueError:
        return command_text.split()


def _token_basename(token: str) -> str:
    """Return the lowercased final path segment of a command token."""
    normalized_token = token.replace(WINDOWS_PATH_SEPARATOR, POSIX_PATH_SEPARATOR)
    return normalized_token.rsplit(POSIX_PATH_SEPARATOR, 1)[-1].lower()


def _is_command_start_position(all_tokens: list[str], token_position: int) -> bool:
    """Report whether the token at token_position begins a shell command.

    A command begins at the first token, or right after a command separator such
    as ``&&`` or ``;`` — so a git word that is only an argument to another command
    (``echo git commit``) does not read as a git invocation.

    Args:
        all_tokens: The tokenized command.
        token_position: The index of the token under test.

    Returns:
        True when the token starts a command, False when it is an argument.
    """
    if token_position == 0:
        return True
    return all_tokens[token_position - 1] in ALL_COMMAND_SEPARATOR_TOKENS


def _first_subcommand_after(all_tokens: list[str], git_token_position: int) -> str:
    """Return the git subcommand following the git token, skipping global flags."""
    cursor = git_token_position + 1
    total_token_count = len(all_tokens)
    while cursor < total_token_count:
        candidate_token = all_tokens[cursor]
        if candidate_token in ALL_ARGUMENT_TAKING_GLOBAL_FLAGS:
            cursor += FLAG_WITH_VALUE_TOKEN_SPAN
            continue
        if candidate_token.startswith(FLAG_TOKEN_PREFIX):
            cursor += 1
            continue
        return candidate_token.lower()
    return ""


def is_git_commit_or_push_command(command_text: str) -> bool:
    """Report whether a shell command runs ``git commit`` or ``git push``.

    ::

        "git commit -m x"      -> True
        "git -C /repo push"    -> True
        "cd repo && git push"  -> True
        "echo git commit"      -> False
        "git status"           -> False

    The command is tokenized. At each command-start git executable token the walk
    steps past the global flags to the first subcommand, which decides the match.

    Args:
        command_text: The Bash command string from the tool payload.

    Returns:
        True when a git commit or push subcommand appears at a command boundary.
    """
    all_tokens = _tokenize_command(command_text)
    for each_position in range(len(all_tokens)):
        if not _is_command_start_position(all_tokens, each_position):
            continue
        if _token_basename(all_tokens[each_position]) not in ALL_GIT_EXECUTABLE_TOKENS:
            continue
        if _first_subcommand_after(all_tokens, each_position) in ALL_REMINDER_TRIGGER_SUBCOMMANDS:
            return True
    return False


def _command_text_from_payload(payload_by_field: dict[str, object]) -> str:
    """Return the Bash command string from the tool payload, or empty when absent."""
    tool_input = payload_by_field.get(TOOL_INPUT_PAYLOAD_KEY, {})
    if not isinstance(tool_input, dict):
        return ""
    command_value = tool_input.get(COMMAND_INPUT_KEY, "")
    return command_value if isinstance(command_value, str) else ""


def build_reminder_payload() -> dict[str, dict[str, str]]:
    """Return the allow payload carrying the tracker reminder as additionalContext."""
    return {
        HOOK_SPECIFIC_OUTPUT_KEY: {
            HOOK_EVENT_NAME_KEY: PRE_TOOL_USE_EVENT_NAME,
            PERMISSION_DECISION_KEY: ALLOW_PERMISSION_DECISION,
            ADDITIONAL_CONTEXT_KEY: ISSUE_TRACKER_COMMIT_REMINDER_TEXT,
        }
    }


def main() -> None:
    """Emit the tracker reminder on a git commit or push, else exit silently."""
    payload = read_hook_input_dictionary_from_stdin()
    if payload is None:
        sys.exit(0)
    command_text = _command_text_from_payload(payload)
    if not is_git_commit_or_push_command(command_text):
        sys.exit(0)
    sys.stdout.write(json.dumps(build_reminder_payload()) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
