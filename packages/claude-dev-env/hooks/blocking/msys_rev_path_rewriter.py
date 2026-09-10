#!/usr/bin/env python3
"""PreToolUse rewriter: keep Git Bash from converting a ``<rev>:<path>`` argument.

Git Bash rewrites a git argument such as ``origin/main:.claude/settings.json``
into a backslash-separated form joined by a semicolon before git sees it, and
git then fails with ``fatal: ambiguous argument``. This hook reads the command
before it runs, finds every token MSYS would convert, and prepends one
``export MSYS2_ARG_CONV_EXCL='<rev1>:;<rev2>:'; `` naming exactly those
prefixes. Every other argument in the command keeps converting as before.

A token is converted only when the part before its first colon carries a slash
and the part after that colon opens a repository-root path, so ``HEAD:.gitignore``
and ``origin/main:packages/app.py`` both reach git untouched and neither is
collected.

Quiet branches, each emitting nothing: a non-Bash tool, a command that already
names one of the MSYS conversion variables, and a command from which no prefix
was collected.

Hosted by ``blocking/bash_pre_tool_use_dispatcher.py``, which carries the
``updatedInput`` this hook prints through to the harness.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

try:
    _hooks_root_directory = str(Path(__file__).resolve().parent.parent)
    if _hooks_root_directory not in sys.path:
        sys.path.insert(0, _hooks_root_directory)
    from hooks_constants.bash_pre_tool_use_dispatcher_constants import BASH_TOOL_NAME
    from hooks_constants.msys_path_conversion_advisor_constants import (
        ALL_MSYS_PATH_CONVERSION_VARIABLE_NAMES,
    )
    from hooks_constants.msys_rev_path_rewriter_constants import (
        ALL_CONVERTED_PATH_START_CHARACTERS,
        ALL_REVISION_FORBIDDEN_CHARACTERS,
        ALL_UNCONVERTED_PATH_START_PREFIXES,
        EXCLUSION_EXPORT_TEMPLATE,
        EXCLUSION_PREFIX_JOIN_SEPARATOR,
        GIT_PROGRAM_NAME,
        REVISION_PATH_SEPARATOR,
        REVISION_PATH_SPLIT_COUNT,
        REVISION_SLASH_CHARACTER,
    )
    from hooks_constants.pre_tool_use_allow_output import (
        write_pre_tool_use_allow_to_stdout,
    )
    from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
    from hooks_constants.shell_command_segments import (
        effective_leading_program,
        split_into_segments,
        token_basename,
    )
except ImportError as import_error:
    raise ImportError(
        "The MSYS revision-path rewriter cannot import its dependencies; "
        "ensure the hooks directory is importable."
    ) from import_error


def _all_git_segment_tokens(command: str) -> list[list[str]]:
    """Return the token lists of the command's segments that run git."""
    try:
        all_command_tokens = shlex.split(command, posix=True)
    except ValueError:
        all_command_tokens = command.split()
    all_git_segments: list[list[str]] = []
    for each_segment in split_into_segments(all_command_tokens):
        program_token = effective_leading_program(each_segment)
        if program_token is None:
            continue
        if token_basename(program_token) == GIT_PROGRAM_NAME:
            all_git_segments.append(each_segment)
    return all_git_segments


def _is_revision_shaped(revision_text: str) -> bool:
    """Return True when the text can name a git revision.

    ::

        origin/main                 -> True
        HEAD                        -> False, no slash
        don't touch a/b             -> False, a quoted message, not a revision

    Args:
        revision_text: The part of a token before its first colon.
    """
    if not revision_text or REVISION_SLASH_CHARACTER not in revision_text:
        return False
    if any(each_character.isspace() for each_character in revision_text):
        return False
    return not any(
        each_character in revision_text for each_character in ALL_REVISION_FORBIDDEN_CHARACTERS
    )


def _converted_revision_prefix(token: str) -> str | None:
    """Return the ``<rev>:`` prefix MSYS would convert in this token, or None.

    Args:
        token: One shell token from a git segment.
    """
    if REVISION_PATH_SEPARATOR not in token:
        return None
    revision_text, path_text = token.split(REVISION_PATH_SEPARATOR, REVISION_PATH_SPLIT_COUNT)
    if not _is_revision_shaped(revision_text):
        return None
    if not path_text.startswith(ALL_CONVERTED_PATH_START_CHARACTERS):
        return None
    if path_text.startswith(ALL_UNCONVERTED_PATH_START_PREFIXES):
        return None
    return revision_text + REVISION_PATH_SEPARATOR


def _extend_with_new_prefixes(
    all_ordered_prefixes: list[str], all_segment_tokens: list[str]
) -> None:
    """Append each convertible prefix this segment adds, skipping repeats.

    Args:
        all_ordered_prefixes: The prefixes collected so far, appended in place.
        all_segment_tokens: One git segment's shell tokens.
    """
    for each_token in all_segment_tokens:
        revision_prefix = _converted_revision_prefix(each_token)
        if revision_prefix is not None and revision_prefix not in all_ordered_prefixes:
            all_ordered_prefixes.append(revision_prefix)


def all_exclusion_prefixes(command: str) -> tuple[str, ...]:
    """Return the ``<rev>:`` prefixes MSYS would convert, deduplicated in order.

    Args:
        command: The Bash command text the agent is about to run.

    Returns:
        Each distinct prefix in first-appearance order, empty when the command
        carries no token Git Bash would convert.
    """
    all_ordered_prefixes: list[str] = []
    for each_segment in _all_git_segment_tokens(command):
        _extend_with_new_prefixes(all_ordered_prefixes, each_segment)
    return tuple(all_ordered_prefixes)


def command_with_exclusion_export(command: str) -> str:
    """Return the command prefixed with the surgical exclusion export.

    Returns the command unchanged when it already names an MSYS conversion
    variable or when no convertible token was found.

    Args:
        command: The Bash command text the agent is about to run.
    """
    if any(
        each_variable_name in command
        for each_variable_name in ALL_MSYS_PATH_CONVERSION_VARIABLE_NAMES
    ):
        return command
    all_prefixes = all_exclusion_prefixes(command)
    if not all_prefixes:
        return command
    export_prefix = EXCLUSION_EXPORT_TEMPLATE.format(
        all_prefixes=EXCLUSION_PREFIX_JOIN_SEPARATOR.join(all_prefixes)
    )
    return export_prefix + command


def main() -> None:
    """Emit an allow carrying the exclusion-prefixed command, or stay quiet."""
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None or hook_payload.get("tool_name") != BASH_TOOL_NAME:
        return
    tool_input = hook_payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    command = tool_input.get("command", "")
    if not isinstance(command, str):
        return
    rewritten_command = command_with_exclusion_export(command)
    if rewritten_command == command:
        return
    write_pre_tool_use_allow_to_stdout({**tool_input, "command": rewritten_command})


if __name__ == "__main__":
    main()
