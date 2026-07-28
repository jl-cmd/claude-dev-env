#!/usr/bin/env python3
"""Resolve the gate base that the pre-push hook hands to the CODE_RULES gate.

Git names the pushed remote in the hook's first argument, so every reference
built here keys on that name: the remote's symbolic head first, then the
candidate default branches that exist under the same remote.

The caller passes its own git seam, so a specification drives these functions
with a table of references in place of a repository.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from git_hooks_constants import (
    ALL_FALLBACK_REMOTE_DEFAULT_BRANCH_NAMES,
    ALL_REMOTE_URL_MARKERS,
    COMMIT_OBJECT_NAME_SUFFIX,
    DEFAULT_REMOTE_BASE_REFERENCE,
    DEFAULT_REMOTE_NAME,
    GIT_COMMAND_SUCCESS_EXIT_CODE,
    GIT_FOR_EACH_REF_SUBCOMMAND,
    GIT_QUIET_FLAG,
    GIT_REFERENCE_SHORT_NAME_FORMAT_ARGUMENT,
    GIT_REV_PARSE_SUBCOMMAND,
    GIT_REV_PARSE_VERIFY_FLAG,
    GIT_SYMBOLIC_REFERENCE_SUBCOMMAND,
    REMOTE_BRANCH_SHORT_NAME_TEMPLATE,
    REMOTE_HEAD_SYMBOLIC_REFERENCE_TEMPLATE,
    REMOTE_NAME_ARGUMENT_INDEX,
    REMOTE_REFERENCE_NAME_PREFIX,
    UNRESOLVABLE_BASE_REFERENCE_MESSAGE,
)

AskGit = Callable[[list[str]], tuple[int, str]]


def resolve_remote_name_from_arguments(all_command_line_arguments: list[str]) -> str:
    """Name the remote this push targets from the arguments git passed.

    ::

        ["pre-push", "upstream", "https://host/owner.git"] -> "upstream"
        ["pre-push", "https://host/owner.git", ...]        -> "origin"

    Git passes a remote name for a named remote and a URL for an ad-hoc push.
    A URL carries a colon or a slash, which a remote name never does, so a URL
    falls back to the default remote.

    Args:
        all_command_line_arguments: The hook's own argument list.

    Returns:
        The remote name that every reference here is built from.
    """
    remote_name_argument_index = REMOTE_NAME_ARGUMENT_INDEX
    if len(all_command_line_arguments) <= remote_name_argument_index:
        return DEFAULT_REMOTE_NAME
    pushed_argument = all_command_line_arguments[remote_name_argument_index].strip()
    if not pushed_argument:
        return DEFAULT_REMOTE_NAME
    if any(each_marker in pushed_argument for each_marker in ALL_REMOTE_URL_MARKERS):
        return DEFAULT_REMOTE_NAME
    return pushed_argument


def _names_a_commit(reference_name: str, ask_git: AskGit) -> bool:
    """Report whether git resolves a reference name to a commit."""
    exit_code, _ = ask_git(
        [
            GIT_REV_PARSE_SUBCOMMAND,
            GIT_REV_PARSE_VERIFY_FLAG,
            GIT_QUIET_FLAG,
            reference_name + COMMIT_OBJECT_NAME_SUFFIX,
        ]
    )
    return exit_code == GIT_COMMAND_SUCCESS_EXIT_CODE


def _first_existing_candidate_branch(remote_name: str, ask_git: AskGit) -> str | None:
    """Name the first candidate default branch that exists under a remote.

    Git lists matching references sorted by reference name, so the candidate
    order below decides which listed name wins.
    """
    all_candidate_short_names = [
        REMOTE_BRANCH_SHORT_NAME_TEMPLATE.format(remote=remote_name, branch=each_branch)
        for each_branch in ALL_FALLBACK_REMOTE_DEFAULT_BRANCH_NAMES
    ]
    _, listed_short_names = ask_git(
        [
            GIT_FOR_EACH_REF_SUBCOMMAND,
            GIT_REFERENCE_SHORT_NAME_FORMAT_ARGUMENT,
            *(
                REMOTE_REFERENCE_NAME_PREFIX + each_short_name
                for each_short_name in all_candidate_short_names
            ),
        ]
    )
    all_existing_short_names = set(listed_short_names.split())
    for each_candidate_short_name in all_candidate_short_names:
        if each_candidate_short_name in all_existing_short_names:
            return each_candidate_short_name
    return None


def _remote_default_branch_reference(remote_name: str, ask_git: AskGit) -> str | None:
    """Name a remote's default branch from its symbolic ref, then candidates."""
    exit_code, symbolic_target = ask_git(
        [
            GIT_SYMBOLIC_REFERENCE_SUBCOMMAND,
            GIT_QUIET_FLAG,
            REMOTE_HEAD_SYMBOLIC_REFERENCE_TEMPLATE.format(remote=remote_name),
        ]
    )
    if exit_code == GIT_COMMAND_SUCCESS_EXIT_CODE and symbolic_target:
        return symbolic_target.removeprefix(REMOTE_REFERENCE_NAME_PREFIX)
    return _first_existing_candidate_branch(remote_name, ask_git)


def _report_unresolvable_base(base_reference: str, remote_name: str) -> None:
    """Tell the pusher which remote head to set so the gate gains a base."""
    sys.stderr.write(
        UNRESOLVABLE_BASE_REFERENCE_MESSAGE.format(reference=base_reference, remote=remote_name)
        + "\n"
    )


def resolve_usable_base_reference(
    base_reference: str, remote_name: str, ask_git: AskGit
) -> str | None:
    """Turn the gate base into a name git can actually resolve.

    ::

        "origin/HEAD" on a clone that has it   -> "origin/HEAD"
        "origin/HEAD" on a clone that lacks it -> "origin/main"
        a commit name git does not know        -> None

    Args:
        base_reference: The gate base drawn from the push's stdin lines.
        remote_name: The remote git named in the hook's arguments.
        ask_git: The seam that runs a git command and reads its output.

    Returns:
        A reference git resolves, or None when no such reference is found.
    """
    if base_reference != DEFAULT_REMOTE_BASE_REFERENCE:
        return base_reference
    if _names_a_commit(base_reference, ask_git):
        return base_reference
    default_branch_reference = _remote_default_branch_reference(remote_name, ask_git)
    if default_branch_reference is None:
        _report_unresolvable_base(base_reference, remote_name)
    return default_branch_reference
