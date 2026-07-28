"""Specifications for the pre-push hook's remote base reference resolution.

A fresh clone leaves ``origin/HEAD`` unset, so the gate base the hook hands to
``code_rules_gate.py`` names an object git cannot resolve and the push aborts.
These specifications pin the fallback to the remote's default branch.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

import git_hooks_constants
import pre_push


RESOLVED_REMOTE_MAIN_REFERENCE: str = "origin/main"
RESOLVED_REMOTE_MASTER_REFERENCE: str = "origin/master"
REMOTE_HEAD_SYMBOLIC_TARGET: str = "refs/remotes/origin/main"
CONCRETE_REMOTE_OBJECT_NAME: str = "1" * 40
GIT_COMMAND_SUCCESS_CODE: int = 0
GIT_COMMAND_FAILURE_CODE: int = 1
EMPTY_COMMAND_OUTPUT: str = ""


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
        requested_reference = command_arguments[-1].removesuffix(
            git_hooks_constants.COMMIT_OBJECT_NAME_SUFFIX
        )
        if requested_reference in all_resolvable_references:
            return GIT_COMMAND_SUCCESS_CODE, CONCRETE_REMOTE_OBJECT_NAME
        return GIT_COMMAND_FAILURE_CODE, EMPTY_COMMAND_OUTPUT

    return fake_run_git_text_command


def _install_fake_git(
    monkeypatch: pytest.MonkeyPatch,
    all_resolvable_references: set[str],
    symbolic_reference_target: str | None,
) -> list[list[str]]:
    """Replace the hook's git seam with a table-driven fake.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        all_resolvable_references: Reference names ``rev-parse`` resolves.
        symbolic_reference_target: The target ``symbolic-ref`` reports, or None
            when the symbolic reference is unset.

    Returns:
        The list recording each argument list the hook passes to git.
    """
    all_recorded_command_arguments: list[list[str]] = []
    monkeypatch.setattr(
        pre_push,
        "run_git_text_command",
        _build_fake_git(
            all_resolvable_references,
            symbolic_reference_target,
            all_recorded_command_arguments,
        ),
    )
    return all_recorded_command_arguments


def should_keep_the_base_reference_when_git_resolves_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_git(
        monkeypatch,
        all_resolvable_references={git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE},
        symbolic_reference_target=None,
    )
    resolved_reference = pre_push.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE
    )
    assert resolved_reference == git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE


def should_use_the_symbolic_target_when_remote_head_is_unresolvable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_git(
        monkeypatch,
        all_resolvable_references={RESOLVED_REMOTE_MAIN_REFERENCE},
        symbolic_reference_target=REMOTE_HEAD_SYMBOLIC_TARGET,
    )
    resolved_reference = pre_push.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE
    )
    assert resolved_reference == RESOLVED_REMOTE_MAIN_REFERENCE


def should_fall_back_to_a_candidate_when_the_symbolic_reference_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_git(
        monkeypatch,
        all_resolvable_references={RESOLVED_REMOTE_MASTER_REFERENCE},
        symbolic_reference_target=None,
    )
    resolved_reference = pre_push.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE
    )
    assert resolved_reference == RESOLVED_REMOTE_MASTER_REFERENCE


def should_report_no_usable_reference_when_nothing_resolves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_git(
        monkeypatch,
        all_resolvable_references=set(),
        symbolic_reference_target=None,
    )
    resolved_reference = pre_push.resolve_usable_base_reference(
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE
    )
    assert resolved_reference is None


def should_pass_a_concrete_object_name_through_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_git(
        monkeypatch,
        all_resolvable_references=set(),
        symbolic_reference_target=REMOTE_HEAD_SYMBOLIC_TARGET,
    )
    resolved_reference = pre_push.resolve_usable_base_reference(CONCRETE_REMOTE_OBJECT_NAME)
    assert resolved_reference == CONCRETE_REMOTE_OBJECT_NAME


def should_ask_git_nothing_about_a_concrete_object_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_recorded_command_arguments = _install_fake_git(
        monkeypatch,
        all_resolvable_references=set(),
        symbolic_reference_target=REMOTE_HEAD_SYMBOLIC_TARGET,
    )
    pre_push.resolve_usable_base_reference(CONCRETE_REMOTE_OBJECT_NAME)
    assert all_recorded_command_arguments == []


def should_ask_git_to_verify_the_reference_as_a_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_recorded_command_arguments = _install_fake_git(
        monkeypatch,
        all_resolvable_references={git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE},
        symbolic_reference_target=None,
    )
    pre_push.resolve_usable_base_reference(git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE)
    first_command_arguments = all_recorded_command_arguments[0]
    assert first_command_arguments[-1] == (
        git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE
        + git_hooks_constants.COMMIT_OBJECT_NAME_SUFFIX
    )
