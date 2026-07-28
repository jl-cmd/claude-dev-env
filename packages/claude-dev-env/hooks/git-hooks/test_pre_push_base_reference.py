"""Specifications for the pre-push hook's remote base reference resolution.

A clone leaves ``origin/HEAD`` unset, so the gate base the hook hands to
``code_rules_gate.py`` names an object git cannot resolve and the push aborts.
These specifications pin the fallback to the default branch of the remote git
names in the hook's arguments, across every candidate default branch name.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

import git_hooks_constants
import pre_push_base_reference


RESOLVED_REMOTE_MAIN_REFERENCE: str = "origin/main"
RESOLVED_REMOTE_MASTER_REFERENCE: str = "origin/master"
RESOLVED_REMOTE_TRUNK_REFERENCE: str = "origin/trunk"
REMOTE_HEAD_SYMBOLIC_TARGET: str = "refs/remotes/origin/main"
UPSTREAM_REMOTE_NAME: str = "upstream"
RESOLVED_UPSTREAM_MAIN_REFERENCE: str = "upstream/main"
UPSTREAM_HEAD_SYMBOLIC_TARGET: str = "refs/remotes/upstream/main"
HOOK_INVOCATION_NAME: str = "pre-push"
PUSHED_REMOTE_URL: str = "https://example.invalid/owner/repository.git"
SSH_PUSHED_REMOTE_URL: str = "git@example.invalid:owner/repository.git"
CONCRETE_REMOTE_OBJECT_NAME: str = "1" * 40
GIT_COMMAND_SUCCESS_CODE: int = 0
GIT_COMMAND_FAILURE_CODE: int = 1
EMPTY_COMMAND_OUTPUT: str = ""
LISTING_LINE_SEPARATOR: str = "\n"


def _list_existing_short_names(
    command_arguments: list[str],
    all_resolvable_references: set[str],
) -> str:
    """Answer a ``for-each-ref`` listing in reverse-sorted order.

    Git sorts a listing by reference name rather than by the pattern order the
    caller passed, so this seam reverses the sort to keep that clash visible.

    Args:
        command_arguments: The git arguments the hook passed.
        all_resolvable_references: The short names this repository holds.

    Returns:
        The newline-joined short names, one per existing reference.
    """
    prefix = git_hooks_constants.REMOTE_REFERENCE_NAME_PREFIX
    all_listed_short_names = [
        each_argument.removeprefix(prefix)
        for each_argument in command_arguments
        if each_argument.removeprefix(prefix) in all_resolvable_references
    ]
    return LISTING_LINE_SEPARATOR.join(sorted(all_listed_short_names, reverse=True))


def _build_fake_git(
    all_resolvable_references: set[str],
    symbolic_reference_target: str | None,
    all_recorded_command_arguments: list[list[str]],
) -> Callable[[list[str]], tuple[int, str]]:
    """Return a git seam that answers from a table rather than a repository."""

    def fake_run_git_text_command(command_arguments: list[str]) -> tuple[int, str]:
        all_recorded_command_arguments.append(list(command_arguments))
        if git_hooks_constants.GIT_SYMBOLIC_REFERENCE_SUBCOMMAND in command_arguments:
            if symbolic_reference_target is None:
                return GIT_COMMAND_FAILURE_CODE, EMPTY_COMMAND_OUTPUT
            return GIT_COMMAND_SUCCESS_CODE, symbolic_reference_target
        if git_hooks_constants.GIT_FOR_EACH_REF_SUBCOMMAND in command_arguments:
            return GIT_COMMAND_SUCCESS_CODE, _list_existing_short_names(
                command_arguments, all_resolvable_references
            )
        requested_reference = command_arguments[-1].removesuffix(
            git_hooks_constants.COMMIT_OBJECT_NAME_SUFFIX
        )
        if requested_reference in all_resolvable_references:
            return GIT_COMMAND_SUCCESS_CODE, CONCRETE_REMOTE_OBJECT_NAME
        return GIT_COMMAND_FAILURE_CODE, EMPTY_COMMAND_OUTPUT

    return fake_run_git_text_command


def _build_recording_git(
    all_resolvable_references: set[str],
    symbolic_reference_target: str | None,
) -> tuple[Callable[[list[str]], tuple[int, str]], list[list[str]]]:
    """Build the table-driven git seam together with its call record.

    Args:
        all_resolvable_references: Reference names ``rev-parse`` resolves and
            ``for-each-ref`` lists.
        symbolic_reference_target: The target ``symbolic-ref`` reports, or None
            when the symbolic reference is unset.

    Returns:
        The git seam paired with the list recording each argument list it saw.
    """
    all_recorded_command_arguments: list[list[str]] = []
    ask_git = _build_fake_git(
        all_resolvable_references,
        symbolic_reference_target,
        all_recorded_command_arguments,
    )
    return ask_git, all_recorded_command_arguments


def should_keep_the_base_reference_when_git_resolves_it() -> None:
    ask_git, _ = _build_recording_git(
        {git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE},
        symbolic_reference_target=None,
    )

    resolved_reference = pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        ask_git,
    )

    assert resolved_reference == git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE


def should_use_the_symbolic_target_when_remote_head_is_unresolvable() -> None:
    ask_git, _ = _build_recording_git(
        {RESOLVED_REMOTE_MAIN_REFERENCE},
        symbolic_reference_target=REMOTE_HEAD_SYMBOLIC_TARGET,
    )

    resolved_reference = pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        ask_git,
    )

    assert resolved_reference == RESOLVED_REMOTE_MAIN_REFERENCE


def should_fall_back_to_a_candidate_when_the_symbolic_reference_is_unset() -> None:
    ask_git, _ = _build_recording_git(
        {RESOLVED_REMOTE_MASTER_REFERENCE},
        symbolic_reference_target=None,
    )

    resolved_reference = pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        ask_git,
    )

    assert resolved_reference == RESOLVED_REMOTE_MASTER_REFERENCE


def should_prefer_main_when_the_listing_reports_master_first() -> None:
    ask_git, _ = _build_recording_git(
        {RESOLVED_REMOTE_MAIN_REFERENCE, RESOLVED_REMOTE_MASTER_REFERENCE},
        symbolic_reference_target=None,
    )

    resolved_reference = pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        ask_git,
    )

    assert resolved_reference == RESOLVED_REMOTE_MAIN_REFERENCE


def should_resolve_a_trunk_default_branch() -> None:
    ask_git, _ = _build_recording_git(
        {RESOLVED_REMOTE_TRUNK_REFERENCE},
        symbolic_reference_target=None,
    )

    resolved_reference = pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        ask_git,
    )

    assert resolved_reference == RESOLVED_REMOTE_TRUNK_REFERENCE


def should_resolve_through_a_remote_named_other_than_origin() -> None:
    ask_git, _ = _build_recording_git(
        {RESOLVED_UPSTREAM_MAIN_REFERENCE},
        symbolic_reference_target=UPSTREAM_HEAD_SYMBOLIC_TARGET,
    )

    resolved_reference = pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        UPSTREAM_REMOTE_NAME,
        ask_git,
    )

    assert resolved_reference == RESOLVED_UPSTREAM_MAIN_REFERENCE


def should_list_candidate_branches_under_the_named_remote() -> None:
    ask_git, all_recorded_command_arguments = _build_recording_git(
        {RESOLVED_UPSTREAM_MAIN_REFERENCE},
        symbolic_reference_target=None,
    )

    resolved_reference = pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        UPSTREAM_REMOTE_NAME,
        ask_git,
    )

    listing_command_arguments = all_recorded_command_arguments[-1]
    assert resolved_reference == RESOLVED_UPSTREAM_MAIN_REFERENCE
    assert UPSTREAM_HEAD_SYMBOLIC_TARGET in listing_command_arguments


def should_report_no_usable_reference_when_nothing_resolves() -> None:
    ask_git, _ = _build_recording_git(set(), symbolic_reference_target=None)

    resolved_reference = pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        ask_git,
    )

    assert resolved_reference is None


def should_name_the_pushed_remote_in_the_unresolvable_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ask_git, _ = _build_recording_git(set(), symbolic_reference_target=None)

    pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        UPSTREAM_REMOTE_NAME,
        ask_git,
    )

    captured_streams = capsys.readouterr()
    assert UPSTREAM_REMOTE_NAME in captured_streams.err


def should_pass_a_concrete_object_name_through_untouched() -> None:
    ask_git, _ = _build_recording_git(
        set(), symbolic_reference_target=REMOTE_HEAD_SYMBOLIC_TARGET
    )

    resolved_reference = pre_push_base_reference.resolve_usable_base_reference(
        CONCRETE_REMOTE_OBJECT_NAME,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        ask_git,
    )

    assert resolved_reference == CONCRETE_REMOTE_OBJECT_NAME


def should_ask_git_nothing_about_a_concrete_object_name() -> None:
    ask_git, all_recorded_command_arguments = _build_recording_git(
        set(), symbolic_reference_target=REMOTE_HEAD_SYMBOLIC_TARGET
    )

    pre_push_base_reference.resolve_usable_base_reference(
        CONCRETE_REMOTE_OBJECT_NAME,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        ask_git,
    )

    assert all_recorded_command_arguments == []


def should_ask_git_to_verify_the_reference_as_a_commit() -> None:
    ask_git, all_recorded_command_arguments = _build_recording_git(
        {git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE},
        symbolic_reference_target=None,
    )

    pre_push_base_reference.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE,
        git_hooks_constants.DEFAULT_REMOTE_NAME,
        ask_git,
    )

    first_command_arguments = all_recorded_command_arguments[0]
    assert first_command_arguments[-1] == (
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE
        + git_hooks_constants.COMMIT_OBJECT_NAME_SUFFIX
    )


def test_reads_the_remote_name_from_the_push_arguments() -> None:
    resolved_remote_name = pre_push_base_reference.resolve_remote_name_from_arguments(
        [HOOK_INVOCATION_NAME, UPSTREAM_REMOTE_NAME, PUSHED_REMOTE_URL]
    )

    assert resolved_remote_name == UPSTREAM_REMOTE_NAME


def test_uses_the_default_remote_when_a_url_takes_the_remote_position() -> None:
    resolved_remote_name = pre_push_base_reference.resolve_remote_name_from_arguments(
        [HOOK_INVOCATION_NAME, PUSHED_REMOTE_URL, PUSHED_REMOTE_URL]
    )

    assert resolved_remote_name == git_hooks_constants.DEFAULT_REMOTE_NAME


def test_uses_the_default_remote_when_an_ssh_url_takes_the_remote_position() -> None:
    resolved_remote_name = pre_push_base_reference.resolve_remote_name_from_arguments(
        [HOOK_INVOCATION_NAME, SSH_PUSHED_REMOTE_URL, SSH_PUSHED_REMOTE_URL]
    )

    assert resolved_remote_name == git_hooks_constants.DEFAULT_REMOTE_NAME


def test_uses_the_default_remote_when_the_push_arguments_are_empty() -> None:
    resolved_remote_name = pre_push_base_reference.resolve_remote_name_from_arguments(
        [HOOK_INVOCATION_NAME]
    )

    assert resolved_remote_name == git_hooks_constants.DEFAULT_REMOTE_NAME
