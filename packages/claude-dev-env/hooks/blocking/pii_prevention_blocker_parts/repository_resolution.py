"""Resolve the repository a git-commit command targets, not the session cwd.

The gate must scan the repository the command names, so a commit that names a
healthy repo is scanned even when the session working directory is gone::

    git -C /a -C sub commit    ->  /a/sub   (each -C composes, like chdir)
    git -C /a/b -C /c/d commit ->  /c/d     (a later absolute -C resets)
    cd "/my repo" && git commit ->  /my repo (quoted cd path, shlex-parsed)
    git commit                 ->  None      (falls back to the session cwd)

The session working directory is used only when the command names no path, so a
removed or invalid cwd never blocks a commit that targets a valid repo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    _blocking_directory = str(Path(__file__).resolve().parent.parent)
    _hooks_directory = str(Path(__file__).resolve().parent.parent.parent)
    for each_bootstrap_directory in (_blocking_directory, _hooks_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)
    from block_main_commit import extract_git_working_directory
    from pii_commit_command import (
        _all_command_segments,
        _segment_invokes_git_commit,
        _skip_leading_noop_tokens,
        _strip_token_edge_quotes,
        _token_is_git_binary,
    )
    from pii_prevention_blocker_parts.config.repository_resolution_constants import (
        REPOSITORY_ROOT_UNRESOLVED_CWD_LABEL,
        REPOSITORY_ROOT_UNRESOLVED_REASON_TEMPLATE,
    )

    from hooks_constants.pii_prevention_constants import (
        ALL_VALUE_TAKING_GIT_OPTIONS,
        GIT_OPTION_WITH_VALUE_STEP,
        GIT_WORKING_DIRECTORY_OPTION,
        SINGLE_DASH_OPTION_PREFIX,
    )
except ImportError as import_error:
    raise ImportError(
        "repository_resolution: cannot import its sibling helpers; "
        "ensure the blocking and hooks directories are importable."
    ) from import_error


def _consume_token(
    all_following_tokens: list[str], token_index: int, all_values: list[str]
) -> int | None:
    """Advance past one token, appending any ``-C`` value; None ends the walk."""
    each_token = _strip_token_edge_quotes(all_following_tokens[token_index])
    if each_token == GIT_WORKING_DIRECTORY_OPTION:
        value_index = token_index + 1
        if value_index >= len(all_following_tokens):
            return None
        all_values.append(_strip_token_edge_quotes(all_following_tokens[value_index]))
        return value_index + 1
    if each_token in ALL_VALUE_TAKING_GIT_OPTIONS:
        return token_index + GIT_OPTION_WITH_VALUE_STEP
    if each_token.startswith(SINGLE_DASH_OPTION_PREFIX):
        return token_index + 1
    return None


def _collect_working_directory_values(all_following_tokens: list[str]) -> list[str]:
    """Return every ``-C`` value, in order, from a commit segment's tokens."""
    all_values: list[str] = []
    token_index: int | None = 0
    while token_index is not None and token_index < len(all_following_tokens):
        token_index = _consume_token(all_following_tokens, token_index, all_values)
    return all_values


def _all_commit_working_directory_values(shell_command: str) -> list[str]:
    """Return every ``-C`` value on the command's git-commit segment, in order."""
    for each_segment in _all_command_segments(shell_command):
        if not _segment_invokes_git_commit(each_segment):
            continue
        command_index = _skip_leading_noop_tokens(each_segment)
        if command_index >= len(each_segment):
            continue
        if not _token_is_git_binary(each_segment[command_index]):
            continue
        return _collect_working_directory_values(each_segment[command_index + 1 :])
    return []


def _next_composed_directory(composed_directory: str | None, each_value: str) -> str:
    """Apply one ``-C`` value to the running composition, like a chained chdir."""
    if os.path.isabs(each_value):
        return each_value
    if composed_directory is None:
        return each_value
    return os.path.join(composed_directory, each_value)


def _compose_working_directories(all_values: list[str]) -> str | None:
    """Compose ordered ``-C`` values the way git applies them."""
    composed_directory: str | None = None
    for each_value in all_values:
        composed_directory = _next_composed_directory(composed_directory, each_value)
    return composed_directory


def compose_command_working_directory(shell_command: str) -> str | None:
    """Return the directory a git-commit command targets, or None for the cwd.

    ::

        git -C /a -C sub commit    ->  /a/sub
        cd "/my repo" && git commit ->  /my repo
        git commit                 ->  None

    Multiple ``-C`` values compose in order (a later absolute value resets); a
    leading ``cd``/``pushd`` supplies the target when the command carries no
    ``-C``.

    Args:
        shell_command: Bash or PowerShell tool command string.

    Returns:
        The composed target directory, or None when the command names none and
        the commit runs in the session working directory.
    """
    all_values = _all_commit_working_directory_values(shell_command)
    if all_values:
        return _compose_working_directories(all_values)
    return extract_git_working_directory(shell_command)


def expand_user_directory(directory: str | None) -> str | None:
    """Expand a leading ``~`` in *directory*, passing None through unchanged.

    Args:
        directory: A directory path that may carry a leading ``~``, or None.

    Returns:
        The tilde-expanded path, or None when *directory* is None.
    """
    if directory is None:
        return None
    return os.path.expanduser(directory)


def refusal_reason_for_unresolved_repository(attempted_directory: str | None) -> str:
    """Return the deny reason naming the path whose repository root did not resolve.

    Args:
        attempted_directory: The directory the gate tried to resolve, or None
            when it fell back to the session working directory.

    Returns:
        The deny reason text, naming the attempted path so the reader sees which
        directory failed to resolve.
    """
    attempted_path = attempted_directory or REPOSITORY_ROOT_UNRESOLVED_CWD_LABEL
    return REPOSITORY_ROOT_UNRESOLVED_REASON_TEMPLATE.format(attempted_path=attempted_path)
