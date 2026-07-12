#!/usr/bin/env python3
"""Token-aware git-commit detection reused by ``pii_prevention_blocker``."""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from block_main_commit import extract_git_working_directory  # noqa: E402

from hooks_constants.pii_prevention_constants import (  # noqa: E402
    ALL_BASH_FAMILY_INTERPRETER_BASENAMES,
    ALL_COMMAND_BOUNDARY_NEWLINE_CHARACTERS,
    ALL_GIT_BINARY_BASENAMES,
    ALL_LEADING_SKIPPABLE_COMMAND_TOKENS,
    ALL_ONE_OPERAND_WRAPPER_TOKENS,
    ALL_SHELL_COMMAND_SEPARATOR_TOKENS,
    ALL_SHELL_INTERPRETER_BASENAMES,
    ALL_SHELL_QUOTE_CHARACTERS,
    ALL_VALUE_TAKING_GIT_OPTIONS,
    DOUBLE_DASH_OPTION_PREFIX,
    ENVIRONMENT_ASSIGNMENT_PATTERN,
    GIT_COMMIT_SUBCOMMAND,
    GIT_OPTION_WITH_VALUE_STEP,
    GIT_WORKING_DIRECTORY_OPTION,
    INLINE_COMMAND_FLAG_CLUSTER_CHARACTER,
    INLINE_COMMAND_TOKEN_JOINER,
    LINE_CONTINUATION_PATTERN,
    POWERSHELL_INLINE_COMMAND_FLAG,
    POWERSHELL_LINE_CONTINUATION_PATTERN,
    SHELL_INLINE_COMMAND_FLAG,
    SINGLE_DASH_OPTION_PREFIX,
    SUBSHELL_GROUP_OPEN_TOKEN,
)


def _strip_token_edge_quotes(token_text: str) -> str:
    return token_text.strip("\"'")


def _token_basename_lower(token_text: str) -> str:
    stripped_token = _strip_token_edge_quotes(token_text)
    return re.split(r"[\\/]", stripped_token)[-1].lower()


def _token_is_git_binary(token_text: str) -> bool:
    return _token_basename_lower(token_text) in ALL_GIT_BINARY_BASENAMES


def _token_is_shell_interpreter(token_text: str) -> bool:
    return _token_basename_lower(token_text) in ALL_SHELL_INTERPRETER_BASENAMES


def _token_is_bash_family_interpreter(token_text: str) -> bool:
    return _token_basename_lower(token_text) in ALL_BASH_FAMILY_INTERPRETER_BASENAMES


def _token_is_subshell_group_open(token_text: str) -> bool:
    return token_text == SUBSHELL_GROUP_OPEN_TOKEN


def _token_is_skippable_prefix(token_text: str) -> bool:
    if ENVIRONMENT_ASSIGNMENT_PATTERN.match(token_text):
        return True
    return _token_basename_lower(token_text) in ALL_LEADING_SKIPPABLE_COMMAND_TOKENS


def _following_tokens_invoke_commit(all_following_tokens: list[str]) -> bool:
    token_index = 0
    option_with_value_step = GIT_OPTION_WITH_VALUE_STEP
    while token_index < len(all_following_tokens):
        each_token = _strip_token_edge_quotes(all_following_tokens[token_index])
        option_name = each_token
        has_attached_value = False
        if each_token.startswith(DOUBLE_DASH_OPTION_PREFIX) and "=" in each_token:
            option_name, _, _attached_value = each_token.partition("=")
            has_attached_value = True
        if option_name in ALL_VALUE_TAKING_GIT_OPTIONS:
            if has_attached_value:
                token_index += 1
            else:
                token_index += option_with_value_step
            continue
        if each_token.startswith(SINGLE_DASH_OPTION_PREFIX):
            token_index += 1
            continue
        return each_token.lower() == GIT_COMMIT_SUBCOMMAND
    return False


def _split_shell_command_segments(all_tokens: list[str]) -> list[list[str]]:
    all_segments: list[list[str]] = [[]]
    shell_separators = ALL_SHELL_COMMAND_SEPARATOR_TOKENS
    for each_token in all_tokens:
        if each_token in shell_separators:
            all_segments.append([])
            continue
        all_segments[-1].append(each_token)
    return all_segments


def _tokenize_shell_command(shell_command_piece: str) -> list[str] | None:
    lexer = shlex.shlex(shell_command_piece, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.escape = ""
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return None


def _fallback_segments_by_physical_line(shell_command_piece: str) -> list[list[str]]:
    all_segments: list[list[str]] = []
    for each_physical_line in shell_command_piece.splitlines():
        line_tokens = each_physical_line.split()
        all_segments.extend(_split_shell_command_segments(line_tokens))
    return all_segments


def _segments_for_piece(shell_command_piece: str) -> list[list[str]]:
    piece_tokens = _tokenize_shell_command(shell_command_piece)
    if piece_tokens is None:
        return _fallback_segments_by_physical_line(shell_command_piece)
    return _split_shell_command_segments(piece_tokens)


def _split_on_unquoted_newlines(shell_command: str) -> list[str]:
    all_pieces: list[str] = []
    current_characters: list[str] = []
    active_quote_character = ""
    for each_character in shell_command:
        if active_quote_character:
            if each_character == active_quote_character:
                active_quote_character = ""
            current_characters.append(each_character)
            continue
        if each_character in ALL_SHELL_QUOTE_CHARACTERS:
            active_quote_character = each_character
            current_characters.append(each_character)
            continue
        if each_character in ALL_COMMAND_BOUNDARY_NEWLINE_CHARACTERS:
            all_pieces.append("".join(current_characters))
            current_characters = []
            continue
        current_characters.append(each_character)
    all_pieces.append("".join(current_characters))
    return all_pieces


def _all_command_segments(shell_command: str) -> list[list[str]]:
    collapsed_command = LINE_CONTINUATION_PATTERN.sub("", shell_command)
    collapsed_command = POWERSHELL_LINE_CONTINUATION_PATTERN.sub("", collapsed_command)
    all_segments: list[list[str]] = []
    for each_piece in _split_on_unquoted_newlines(collapsed_command):
        all_segments.extend(_segments_for_piece(each_piece))
    return all_segments


def _token_is_leading_skip_target(token_text: str) -> bool:
    return _token_is_git_binary(token_text) or _token_is_shell_interpreter(token_text)


def _token_is_wrapper_option_flag(token_text: str) -> bool:
    return token_text.startswith(SINGLE_DASH_OPTION_PREFIX)


def _wrapper_leading_operand_count(token_text: str) -> int:
    if _token_basename_lower(token_text) in ALL_ONE_OPERAND_WRAPPER_TOKENS:
        return 1
    return 0


def _flag_value_token_follows(all_segment_tokens: list[str], value_index: int) -> bool:
    if value_index >= len(all_segment_tokens):
        return False
    if not _token_is_leading_skip_target(all_segment_tokens[value_index]):
        return True
    return _later_token_is_leading_skip_target(all_segment_tokens, value_index + 1)


def _later_token_is_leading_skip_target(
    all_segment_tokens: list[str], search_start_index: int
) -> bool:
    for each_token in all_segment_tokens[search_start_index:]:
        if _token_is_leading_skip_target(each_token):
            return True
    return False


def _skip_leading_noop_tokens(all_segment_tokens: list[str]) -> int:
    token_index = 0
    has_skipped_wrapper_prefix = False
    pending_operand_budget = 0
    while token_index < len(all_segment_tokens):
        each_token = all_segment_tokens[token_index]
        if _token_is_subshell_group_open(each_token):
            token_index += 1
            continue
        if _token_is_skippable_prefix(each_token):
            has_skipped_wrapper_prefix = True
            pending_operand_budget += _wrapper_leading_operand_count(each_token)
            token_index += 1
            continue
        if not has_skipped_wrapper_prefix:
            break
        if _token_is_leading_skip_target(each_token):
            break
        if _token_is_wrapper_option_flag(each_token):
            token_index += 1
            if _flag_value_token_follows(all_segment_tokens, token_index):
                token_index += 1
            continue
        if pending_operand_budget > 0:
            pending_operand_budget -= 1
            token_index += 1
            continue
        break
    return token_index


def _token_is_powershell_command_flag_prefix(lowered_token: str) -> bool:
    if lowered_token == SINGLE_DASH_OPTION_PREFIX:
        return False
    return POWERSHELL_INLINE_COMMAND_FLAG.startswith(lowered_token)


def _token_is_interpreter_inline_command_flag(
    token_text: str, interpreter_allows_short_flag_cluster: bool
) -> bool:
    if not token_text.startswith(SINGLE_DASH_OPTION_PREFIX):
        return False
    if token_text.startswith(DOUBLE_DASH_OPTION_PREFIX):
        return False
    lowered_token = token_text.lower()
    if lowered_token == SHELL_INLINE_COMMAND_FLAG:
        return True
    if _token_is_powershell_command_flag_prefix(lowered_token):
        return True
    if not interpreter_allows_short_flag_cluster:
        return False
    clustered_flag_characters = lowered_token[len(SINGLE_DASH_OPTION_PREFIX) :]
    return INLINE_COMMAND_FLAG_CLUSTER_CHARACTER in clustered_flag_characters


def _interpreter_inline_command_invokes_commit(
    interpreter_token: str, all_following_tokens: list[str]
) -> bool:
    allows_short_flag_cluster = _token_is_bash_family_interpreter(interpreter_token)
    token_index = 0
    while token_index < len(all_following_tokens):
        each_token = all_following_tokens[token_index]
        if _token_is_interpreter_inline_command_flag(
            each_token, allows_short_flag_cluster
        ):
            argument_index = token_index + 1
            if argument_index >= len(all_following_tokens):
                return False
            inline_command = INLINE_COMMAND_TOKEN_JOINER.join(
                all_following_tokens[argument_index:]
            )
            return is_git_commit_shell_command(inline_command)
        token_index += 1
    return False


def _segment_invokes_git_commit(all_segment_tokens: list[str]) -> bool:
    command_index = _skip_leading_noop_tokens(all_segment_tokens)
    if command_index >= len(all_segment_tokens):
        return False
    all_following_tokens = all_segment_tokens[command_index + 1 :]
    command_token = all_segment_tokens[command_index]
    if _token_is_shell_interpreter(command_token):
        return _interpreter_inline_command_invokes_commit(
            command_token, all_following_tokens
        )
    if not _token_is_git_binary(command_token):
        return False
    return _following_tokens_invoke_commit(all_following_tokens)


def is_git_commit_shell_command(shell_command: str) -> bool:
    """Report whether *shell_command* invokes git commit (token-aware).

    Each segment is read past its leading noise to the real command word::

        sudo git commit -m x        ->  skip the wrapper, then match commit
        nice -n 10 git commit       ->  skip the wrapper and its flag value
        then git commit -m x        ->  skip the keyword, then match commit
        build & git commit -m x     ->  split on the background operator
        bash -cx "git commit"                     ->  unwrap the bash cluster
        pwsh -ExecutionPolicy Bypass -Command ... ->  skip past the pwsh flag
        (git commit -m x)                         ->  step over the group open

    Skipped leading tokens: a subshell-group open ``(``, env-assignments, shell
    keywords (then, do, else, elif), and wrapper commands (sudo, env, time,
    nice, xargs, command, stdbuf) together with each wrapper's own option flags,
    flag values, and the single leading operand that timeout and flock take
    before their command. A non-wrapper command word between a wrapper and a
    later git commit stops the scan, so the wrapper's own payload command is
    read rather than the trailing git token. Segments split on unquoted control
    separators (including
    a lone ``&`` background operator) and newlines, and the git binary may be
    path-prefixed and carry global flags (no-verify, config, and
    working-directory) before its subcommand. A shell interpreter is unwrapped
    at its inline-command flag by interpreter family: bash and sh take an
    isolated ``-c`` or any short-flag cluster carrying ``c`` (``-lc``, ``-cx``),
    and PowerShell (pwsh, powershell) takes only ``-Command`` or ``-c``, so a
    leading pwsh flag whose name merely contains ``c`` (``-ExecutionPolicy``,
    ``-NonInteractive``) is stepped over until the real ``-Command`` is reached.
    The inline command's remaining tokens rejoin into one string, so an
    unquoted multi-token command is read whole.

    Args:
        shell_command: Bash or PowerShell tool command string.

    Returns:
        True when a command segment invokes git with a commit subcommand.
    """
    if not shell_command or not shell_command.strip():
        return False
    for each_segment in _all_command_segments(shell_command):
        if _segment_invokes_git_commit(each_segment):
            return True
    return False


def _following_tokens_working_directory(all_following_tokens: list[str]) -> str | None:
    token_index = 0
    option_with_value_step = GIT_OPTION_WITH_VALUE_STEP
    while token_index < len(all_following_tokens):
        each_token = _strip_token_edge_quotes(all_following_tokens[token_index])
        if each_token == GIT_WORKING_DIRECTORY_OPTION:
            value_index = token_index + 1
            if value_index >= len(all_following_tokens):
                return None
            return _strip_token_edge_quotes(all_following_tokens[value_index])
        option_name = each_token
        has_attached_value = False
        if each_token.startswith(DOUBLE_DASH_OPTION_PREFIX) and "=" in each_token:
            option_name, _, _attached_value = each_token.partition("=")
            has_attached_value = True
        if option_name in ALL_VALUE_TAKING_GIT_OPTIONS:
            token_index += 1 if has_attached_value else option_with_value_step
            continue
        if each_token.startswith(SINGLE_DASH_OPTION_PREFIX):
            token_index += 1
            continue
        return None
    return None


def _segment_git_commit_working_directory(
    all_segment_tokens: list[str],
) -> str | None:
    command_index = _skip_leading_noop_tokens(all_segment_tokens)
    if command_index >= len(all_segment_tokens):
        return None
    command_token = all_segment_tokens[command_index]
    if not _token_is_git_binary(command_token):
        return None
    all_following_tokens = all_segment_tokens[command_index + 1 :]
    return _following_tokens_working_directory(all_following_tokens)


def extract_git_commit_working_directory(shell_command: str) -> str | None:
    """Return the directory a git-commit command runs in, or None for the CWD.

    Reads the ``-C`` value off the same commit-invoking segment the detector
    matches, so every git-binary shape the detector recognizes resolves too::

        git.exe -C /repoA commit -m x   ->  /repoA
        git -C "C:/repo" commit -m x    ->  C:/repo
        cd /repoB && git commit -m x    ->  /repoB (cd/pushd fallback)
        git commit -m x                 ->  None   (runs in the CWD)

    Args:
        shell_command: Bash or PowerShell tool command string.

    Returns:
        The working directory the commit targets, or None when it uses the CWD.
    """
    for each_segment in _all_command_segments(shell_command):
        if not _segment_invokes_git_commit(each_segment):
            continue
        segment_directory = _segment_git_commit_working_directory(each_segment)
        if segment_directory is not None:
            return segment_directory
    return extract_git_working_directory(shell_command)
