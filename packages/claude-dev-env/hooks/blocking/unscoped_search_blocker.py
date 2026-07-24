#!/usr/bin/env python3
"""PreToolUse hook: deny whole-drive and bare-home filesystem searches.

Blocks Bash/PowerShell commands that walk from an unscoped root — ``find /``,
``find C:\\``, ``find ~``, recursive ``Get-ChildItem`` on a drive root — so a
session cannot thrash the host with millions of handles. Scoped walks under a
project path stay allowed. Parallel shell storms are out of scope for this
detector; the deny message still steers agents to batch shell work.

::

    find / -iname code_rules_gate.py          flag: unscoped root
    find . -iname code_rules_gate.py          ok:   cwd scope
    Get-ChildItem -Path C:\\ -Recurse         flag: recursive drive root
    Get-ChildItem -Path .\\src -Recurse       ok:   project scope
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.shell_command_segments import (  # noqa: E402
    effective_leading_program,
    split_into_segments,
    token_basename,
)
from hooks_constants.unscoped_search_blocker_constants import (  # noqa: E402
    ALL_FIND_EXPRESSION_INTRODUCER_TOKENS,
    ALL_FIND_GLOBAL_OPTION_FLAGS_TAKING_A_VALUE,
    ALL_FIND_GLOBAL_OPTION_FLAGS_WITHOUT_VALUE,
    ALL_FIND_PROGRAM_BASENAMES,
    ALL_GET_CHILD_ITEM_PATH_FLAGS,
    ALL_GET_CHILD_ITEM_PROGRAM_BASENAMES,
    ALL_GET_CHILD_ITEM_RECURSE_FLAGS,
    ALL_SUPPORTED_TOOL_NAMES,
    ALL_UNSCOPED_HOME_LITERALS,
    CALLING_HOOK_NAME,
    CORRECTIVE_MESSAGE,
    DENY_DECISION,
    FIND_GLOBAL_OPTION_VALUE_TOKEN_STRIDE,
    FIND_OPTIMIZATION_LEVEL_OPTION_PREFIX,
    GIT_BASH_DRIVE_ROOT_PATTERN,
    HOOK_EVENT_NAME,
    MINIMUM_FIND_OPTIMIZATION_OPTION_LENGTH,
    PATH_FLAG_AND_VALUE_TOKEN_STRIDE,
    WINDOWS_DRIVE_ROOT_PATTERN,
)


def is_unscoped_search_root(path_token: str) -> bool:
    """Return True when a path token is a whole-drive or bare-home root.

    ::

        /          flag
        /c/        flag  (Git Bash drive root)
        C:\\        flag
        ~          flag
        ./src      ok
        /c/Users/x ok

    Args:
        path_token: One shell token treated as a search start path.

    Returns:
        True when the token names an unscoped filesystem root.
    """
    stripped_path = path_token.strip().strip("\"'")
    if not stripped_path:
        return False
    if stripped_path in ALL_UNSCOPED_HOME_LITERALS:
        return True
    forward_slash_path = stripped_path.replace("\\", "/")
    if forward_slash_path == "/":
        return True
    if GIT_BASH_DRIVE_ROOT_PATTERN.fullmatch(forward_slash_path):
        return True
    if WINDOWS_DRIVE_ROOT_PATTERN.fullmatch(stripped_path):
        return True
    return False


def _tokens_after_leading_program(
    all_segment_tokens: list[str], leading_program: str | None
) -> list[str]:
    if leading_program is None:
        return []
    leading_index = all_segment_tokens.index(leading_program)
    return all_segment_tokens[leading_index + 1 :]


def _is_find_expression_token(token: str) -> bool:
    if token in ALL_FIND_EXPRESSION_INTRODUCER_TOKENS:
        return True
    if token.startswith("-") and not WINDOWS_DRIVE_ROOT_PATTERN.fullmatch(token):
        return True
    return False


def _collect_find_starting_points(all_argument_tokens: list[str]) -> list[str]:
    all_starting_points: list[str] = []
    token_index = 0
    while token_index < len(all_argument_tokens):
        each_token = all_argument_tokens[token_index]
        if each_token in ALL_FIND_GLOBAL_OPTION_FLAGS_WITHOUT_VALUE:
            token_index += 1
            continue
        if each_token in ALL_FIND_GLOBAL_OPTION_FLAGS_TAKING_A_VALUE:
            token_index += FIND_GLOBAL_OPTION_VALUE_TOKEN_STRIDE
            continue
        if (
            each_token.startswith(FIND_OPTIMIZATION_LEVEL_OPTION_PREFIX)
            and len(each_token) >= MINIMUM_FIND_OPTIMIZATION_OPTION_LENGTH
        ):
            token_index += 1
            continue
        if _is_find_expression_token(each_token):
            break
        all_starting_points.append(each_token)
        token_index += 1
    return all_starting_points


def _segment_has_unscoped_find(all_segment_tokens: list[str]) -> bool:
    leading_program = effective_leading_program(all_segment_tokens)
    if leading_program is None:
        return False
    if token_basename(leading_program) not in ALL_FIND_PROGRAM_BASENAMES:
        return False
    all_starting_points = _collect_find_starting_points(
        _tokens_after_leading_program(all_segment_tokens, leading_program)
    )
    return any(
        is_unscoped_search_root(each_start) for each_start in all_starting_points
    )


def _collect_get_child_item_path_tokens(all_argument_tokens: list[str]) -> list[str]:
    all_path_tokens: list[str] = []
    token_index = 0
    while token_index < len(all_argument_tokens):
        each_token = all_argument_tokens[token_index]
        lowered_token = each_token.lower()
        if lowered_token in ALL_GET_CHILD_ITEM_PATH_FLAGS:
            if token_index + 1 < len(all_argument_tokens):
                all_path_tokens.append(all_argument_tokens[token_index + 1])
                token_index += PATH_FLAG_AND_VALUE_TOKEN_STRIDE
                continue
        if each_token.startswith("-"):
            token_index += 1
            continue
        all_path_tokens.append(each_token)
        token_index += 1
    return all_path_tokens


def _segment_has_unscoped_recursive_listing(all_segment_tokens: list[str]) -> bool:
    leading_program = effective_leading_program(all_segment_tokens)
    if leading_program is None:
        return False
    if token_basename(leading_program) not in ALL_GET_CHILD_ITEM_PROGRAM_BASENAMES:
        return False
    all_argument_tokens = _tokens_after_leading_program(
        all_segment_tokens, leading_program
    )
    has_recurse_flag = any(
        each_token.lower() in ALL_GET_CHILD_ITEM_RECURSE_FLAGS
        for each_token in all_argument_tokens
    )
    if not has_recurse_flag:
        return False
    all_path_tokens = _collect_get_child_item_path_tokens(all_argument_tokens)
    if not all_path_tokens:
        return False
    return any(
        is_unscoped_search_root(each_path) for each_path in all_path_tokens
    )


def _all_command_tokenizations(command: str) -> list[list[str]]:
    """Return POSIX and non-POSIX tokenizations so Windows paths stay intact.

    Git Bash commands need POSIX splitting (quote rules). PowerShell paths like
    ``C:\\`` need non-POSIX splitting so the backslash is not an escape. Both
    are tried; an empty or failed split is dropped.
    """
    all_tokenizations: list[list[str]] = []
    for each_posix_mode in (True, False):
        try:
            all_tokens = shlex.split(command, posix=each_posix_mode)
        except ValueError:
            continue
        if all_tokens:
            all_tokenizations.append(all_tokens)
    return all_tokenizations


def find_unscoped_search_violation(command: str) -> str | None:
    """Return the deny message for an unscoped tree walk, or None to allow.

    ::

        find / -iname x.py                     flag
        find packages -iname x.py              ok
        Get-ChildItem -Path C:\\ -Recurse       flag
        Get-ChildItem -Path .\\src -Recurse     ok

    Tokenizes the command under POSIX and non-POSIX shlex modes, splits on shell
    control operators, and evaluates each simple-command segment. A ``find``
    segment with an unscoped starting point denies. A recursive
    ``Get-ChildItem``/``gci``/``dir``/``ls`` segment with an unscoped path
    denies. Returns None when neither tokenization yields tokens.

    Args:
        command: The raw Bash or PowerShell command string from the tool input.

    Returns:
        The corrective deny message when a segment walks from an unscoped root,
        else None.
    """
    for each_tokenization in _all_command_tokenizations(command):
        for each_segment in split_into_segments(each_tokenization):
            if _segment_has_unscoped_find(each_segment):
                return CORRECTIVE_MESSAGE
            if _segment_has_unscoped_recursive_listing(each_segment):
                return CORRECTIVE_MESSAGE
    return None


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ALL_SUPPORTED_TOOL_NAMES:
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    deny_reason = find_unscoped_search_violation(command)
    if deny_reason is None:
        sys.exit(0)

    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": DENY_DECISION,
            "permissionDecisionReason": deny_reason,
        }
    }
    log_hook_block(
        calling_hook_name=CALLING_HOOK_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=deny_reason,
        tool_name=tool_name,
        offending_input_preview=command,
    )
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
