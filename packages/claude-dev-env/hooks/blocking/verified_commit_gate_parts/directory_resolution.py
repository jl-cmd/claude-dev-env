"""Resolve the active directory a ``cd``/``pushd`` verb leaves the shell in.

::

    cd subdir && git commit    -> commit gates against session_dir/subdir
    cd /repo && git commit     -> commit gates against /repo

A gated git invocation with no ``-C``/``--work-tree`` flag runs in whatever
directory the shell is in at that point in the command, so the gate walks
each directory-change verb to know the directory the following commit
actually targets.
"""

from __future__ import annotations

import os
import re

from config.verified_commit_constants import (
    DIRECTORY_CHANGE_OPTION_TERMINATOR,
    DIRECTORY_CHANGE_PATH_OPTIONS,
)
from verified_commit_gate_parts.command_tokenization import strip_token_quotes


def split_option_value(option_token: str) -> tuple[str, str | None]:
    """Split a ``--name=value`` option token into its name and value.

    Args:
        option_token: One quote-stripped token after the ``git`` word.

    Returns:
        The option name and its attached value, or the whole token and None
        when the token carries no ``=`` value.
    """
    if option_token.startswith("--") and "=" in option_token:
        option_name, _, attached_value = option_token.partition("=")
        return (option_name, attached_value)
    return (option_token, None)


def value_after_option(all_following_tokens: list[str], option_index: int) -> str | None:
    """Read the separate value token that follows a value-taking option.

    Args:
        all_following_tokens: Quote-stripped tokens after the ``git`` word.
        option_index: Index of the value-taking option token.

    Returns:
        The next token when one exists, or None at the end of the tokens.
    """
    if option_index + 1 < len(all_following_tokens):
        return all_following_tokens[option_index + 1]
    return None


def expand_home_prefix(directory_token: str) -> str:
    """Expand a leading ``~`` to the home directory the shell would use.

    Git does not expand ``~`` for ``-C`` or ``--work-tree`` and never sees a
    shell's ``cd ~`` expansion, so the gate expands the token itself;
    otherwise it resolves a non-existent ``~/...`` path that git rejects while
    the shell commits in the real home-anchored repo.

    Args:
        directory_token: A directory token that may start with ``~``.

    Returns:
        The token with any leading home prefix expanded, unchanged otherwise.
    """
    if directory_token.startswith("~"):
        return os.path.expanduser(directory_token)
    return directory_token


def is_absolute_directory(directory_token: str) -> bool:
    """Decide whether a directory-change target is already absolute.

    Treats a POSIX root, a Windows drive or UNC root, a leading slash or
    backslash, and a home-relative ``~`` token as absolute so they are used
    as given rather than joined onto the active directory.

    Args:
        directory_token: The destination of a directory-change verb.

    Returns:
        True when the token names an absolute or home-anchored location.
    """
    if directory_token.startswith("~"):
        return True
    if directory_token.startswith(("/", "\\")):
        return True
    return os.path.isabs(directory_token)


def resolve_against(active_directory: str, changed_directory: str) -> str:
    """Resolve a directory-change target against the active directory.

    An absolute or home-anchored target becomes the new active directory; a
    relative target is joined onto it so a ``cd subdir`` gates against the
    session directory's subdirectory rather than a token git would resolve
    against the hook process's own working directory.

    Args:
        active_directory: The directory in effect before this change.
        changed_directory: The destination of a directory-change verb.

    Returns:
        The directory the shell runs in after the change.
    """
    if is_absolute_directory(changed_directory):
        return expand_home_prefix(changed_directory)
    return os.path.join(active_directory, changed_directory)


def argument_tokens_after_verb(command_text: str, match_end: int) -> list[str]:
    """Cut the run of argument tokens that follows a directory-change verb.

    Reads tokens until the first shell command separator (``;``, ``&``,
    ``|``, or a newline), so only the verb's own arguments are returned and a
    following command is left untouched.

    Args:
        command_text: The raw command string from the tool payload.
        match_end: The offset just past the directory-change verb word.

    Returns:
        The quote-aware argument tokens following the verb, in order.
    """
    argument_run_pattern = re.compile(r"[ \t]+((?:\"[^\"]*\"|'[^']*'|[^\s;&|])+)")
    argument_token_pattern = re.compile(r"\"[^\"]*\"|'[^']*'|[^\s;&|]+")
    all_argument_tokens: list[str] = []
    scan_position = match_end
    while True:
        run_match = argument_run_pattern.match(command_text, scan_position)
        if run_match is None:
            return all_argument_tokens
        all_argument_tokens.extend(argument_token_pattern.findall(run_match.group(1)))
        scan_position = run_match.end()


def directory_change_target(command_text: str, match_end: int) -> str | None:
    """Read the destination of a directory-change verb.

    Walks the arguments after the verb, skipping a leading ``--`` terminator
    and consuming the value after a PowerShell path option
    (``-Path``/``-LiteralPath``) so the destination is the path rather than
    the flag. A leading shell operator (``cd && git ...``) means no argument
    and the active directory stays unchanged.

    Args:
        command_text: The raw command string from the tool payload.
        match_end: The offset just past the directory-change verb word.

    Returns:
        The destination path when one follows the verb, or None for a bare
        ``cd`` (a return to the home directory, which the gate ignores).
    """
    all_argument_tokens = argument_tokens_after_verb(command_text, match_end)
    token_index = 0
    while token_index < len(all_argument_tokens):
        each_token = strip_token_quotes(all_argument_tokens[token_index])
        if each_token == DIRECTORY_CHANGE_OPTION_TERMINATOR:
            token_index += 1
            continue
        if each_token.lower() in DIRECTORY_CHANGE_PATH_OPTIONS:
            token_index += 1
            continue
        return each_token
    return None
