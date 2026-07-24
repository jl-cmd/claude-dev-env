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
    ls -r /                                   ok:   reverse sort, not recurse
    ls -R /                                   flag: recursive root listing
    bash -c 'find / -name x'                  flag: string-exec unwrap
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
    ALL_LISTING_PROGRAM_BASENAMES,
    ALL_POWERSHELL_PATH_FLAG_PREFIXES,
    ALL_POWERSHELL_PATH_FLAGS,
    ALL_POWERSHELL_RECURSE_FLAG_PREFIXES,
    ALL_POWERSHELL_RECURSE_FLAGS,
    ALL_STRING_EXEC_COMMAND_FLAGS,
    ALL_STRING_EXECUTING_SHELL_BASENAMES,
    ALL_SUPPORTED_TOOL_NAMES,
    ALL_TRUTHY_RECURSE_COLON_VALUES,
    ALL_UNIX_LS_PROGRAM_BASENAMES,
    ALL_UNIX_LS_RECURSE_FLAGS,
    ALL_UNSCOPED_HOME_LITERALS_CASEFOLD,
    CALLING_HOOK_NAME,
    CORRECTIVE_MESSAGE,
    DENY_DECISION,
    FIND_OPTIMIZATION_LEVEL_OPTION_PREFIX,
    FLAG_AND_VALUE_TOKEN_STRIDE,
    GIT_BASH_DRIVE_ROOT_PATTERN,
    HOOK_EVENT_NAME,
    POSIX_ROOT_ALIAS_PATTERN,
    WINDOWS_DRIVE_ROOT_PATTERN,
)


def is_unscoped_search_root(path_token: str) -> bool:
    """Return True when a path token is a whole-drive or bare-home root.

    ::

        /          flag
        /.         flag  (posix root alias)
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
    if stripped_path.casefold() in ALL_UNSCOPED_HOME_LITERALS_CASEFOLD:
        return True
    forward_slash_path = stripped_path.replace("\\", "/")
    if POSIX_ROOT_ALIAS_PATTERN.fullmatch(forward_slash_path):
        return True
    if GIT_BASH_DRIVE_ROOT_PATTERN.fullmatch(forward_slash_path):
        return True
    if WINDOWS_DRIVE_ROOT_PATTERN.fullmatch(stripped_path):
        return True
    windows_drive_alias = stripped_path.rstrip(".\\/")
    if WINDOWS_DRIVE_ROOT_PATTERN.fullmatch(windows_drive_alias + "\\"):
        return True
    if WINDOWS_DRIVE_ROOT_PATTERN.fullmatch(windows_drive_alias):
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
    return token.startswith("-")


def _collect_find_starting_points(all_argument_tokens: list[str]) -> list[str]:
    all_starting_points: list[str] = []
    token_index = 0
    while token_index < len(all_argument_tokens):
        each_token = all_argument_tokens[token_index]
        if each_token in ALL_FIND_GLOBAL_OPTION_FLAGS_WITHOUT_VALUE:
            token_index += 1
            continue
        if each_token in ALL_FIND_GLOBAL_OPTION_FLAGS_TAKING_A_VALUE:
            if token_index + 1 >= len(all_argument_tokens):
                token_index += 1
                continue
            next_token = all_argument_tokens[token_index + 1]
            if is_unscoped_search_root(next_token) or _is_find_expression_token(
                next_token
            ):
                token_index += 1
                continue
            token_index += FLAG_AND_VALUE_TOKEN_STRIDE
            continue
        if each_token.startswith(FIND_OPTIMIZATION_LEVEL_OPTION_PREFIX):
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


def _token_is_recurse_flag(token: str, program_basename: str) -> bool:
    if program_basename in ALL_UNIX_LS_PROGRAM_BASENAMES:
        return token in ALL_UNIX_LS_RECURSE_FLAGS
    lowered_token = token.lower()
    if lowered_token in ALL_POWERSHELL_RECURSE_FLAGS:
        return True
    for each_prefix in ALL_POWERSHELL_RECURSE_FLAG_PREFIXES:
        if lowered_token.startswith(each_prefix):
            colon_value = lowered_token[len(each_prefix) :]
            return colon_value in ALL_TRUTHY_RECURSE_COLON_VALUES
    return False


def _path_value_from_path_flag_token(token: str) -> str | None:
    lowered_token = token.lower()
    for each_prefix in ALL_POWERSHELL_PATH_FLAG_PREFIXES:
        if lowered_token.startswith(each_prefix):
            return token[len(each_prefix) :]
    return None


def _collect_get_child_item_path_tokens(all_argument_tokens: list[str]) -> list[str]:
    all_path_tokens: list[str] = []
    token_index = 0
    while token_index < len(all_argument_tokens):
        each_token = all_argument_tokens[token_index]
        lowered_token = each_token.lower()
        path_from_glued_flag = _path_value_from_path_flag_token(each_token)
        if path_from_glued_flag is not None:
            if path_from_glued_flag:
                all_path_tokens.append(path_from_glued_flag)
            token_index += 1
            continue
        if lowered_token in ALL_POWERSHELL_PATH_FLAGS:
            if token_index + 1 < len(all_argument_tokens):
                all_path_tokens.append(all_argument_tokens[token_index + 1])
                token_index += FLAG_AND_VALUE_TOKEN_STRIDE
                continue
        if lowered_token == "/s" or each_token.startswith("-"):
            token_index += 1
            continue
        all_path_tokens.append(each_token)
        token_index += 1
    return all_path_tokens


def _segment_has_unscoped_recursive_listing(all_segment_tokens: list[str]) -> bool:
    leading_program = effective_leading_program(all_segment_tokens)
    if leading_program is None:
        return False
    program_basename = token_basename(leading_program)
    if program_basename not in ALL_LISTING_PROGRAM_BASENAMES:
        return False
    all_argument_tokens = _tokens_after_leading_program(
        all_segment_tokens, leading_program
    )
    has_recurse_flag = any(
        _token_is_recurse_flag(each_token, program_basename)
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


def _string_exec_inner_command(all_segment_tokens: list[str]) -> str | None:
    leading_program = effective_leading_program(all_segment_tokens)
    if leading_program is None:
        return None
    if token_basename(leading_program) not in ALL_STRING_EXECUTING_SHELL_BASENAMES:
        return None
    all_argument_tokens = _tokens_after_leading_program(
        all_segment_tokens, leading_program
    )
    token_index = 0
    while token_index < len(all_argument_tokens):
        each_token = all_argument_tokens[token_index]
        if each_token.lower() in ALL_STRING_EXEC_COMMAND_FLAGS:
            if token_index + 1 < len(all_argument_tokens):
                return all_argument_tokens[token_index + 1]
            return None
        token_index += 1
    return None


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
        bash -c 'find / -name x'               flag
        ls -r /                                ok
        ls -R /                                flag

    Tokenizes the command under POSIX and non-POSIX shlex modes, splits on shell
    control operators, and evaluates each simple-command segment. A ``find``
    segment with an unscoped starting point denies. A recursive listing segment
    (PowerShell ``Get-ChildItem``/``gci``/``dir`` or Unix ``ls -R``) with an
    unscoped path denies. A ``bash -c`` / ``pwsh -Command`` wrapper re-runs the
    check on its string argument. Returns None when neither tokenization yields
    tokens.

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
            inner_command = _string_exec_inner_command(each_segment)
            if inner_command is not None:
                nested_denial = find_unscoped_search_violation(inner_command)
                if nested_denial is not None:
                    return nested_denial
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
