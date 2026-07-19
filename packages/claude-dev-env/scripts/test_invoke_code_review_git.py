"""Working-tree dirty detection and the git status porcelain command."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

import invoke_code_review as invoker
from _code_review_test_support import (
    DIRTY_FILE_CONTENTS,
    DIRTY_FILE_NAME,
    FIXTURE_CHAIN_RETURNCODE,
    FIXTURE_GIT_STATUS_FAILURE_RETURNCODE,
    FIXTURE_SERVED_COMMAND,
    FIXTURE_SESSION_OPUS,
    HOST_PROFILE_THIRD_PARTY,
    claude_served,
    init_git_repository,
    install_seams,
    run_review,
)
from dev_env_scripts_constants.code_review_constants import (
    GIT_BINARY,
    GIT_PORCELAIN_FLAG,
    GIT_STATUS_SUBCOMMAND,
    MODE_CHAIN,
)


def test_dirty_tree_true_after_chain_writes_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=claude_served(),
        should_dirty_tree_on_chain=True,
        working_directory=working_directory,
    )

    review_outcome = run_review(working_directory, session_model=FIXTURE_SESSION_OPUS)

    assert review_outcome.mode == MODE_CHAIN
    assert review_outcome.is_dirty_tree is True
    assert review_outcome.served_command == FIXTURE_SERVED_COMMAND
    assert review_outcome.returncode == FIXTURE_CHAIN_RETURNCODE


def test_dirty_tree_false_when_chain_leaves_tree_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=claude_served(),
        should_dirty_tree_on_chain=False,
        working_directory=working_directory,
    )

    review_outcome = run_review(working_directory, session_model=FIXTURE_SESSION_OPUS)

    assert review_outcome.is_dirty_tree is False


def test_is_working_tree_dirty_against_real_git_repo(tmp_path: Path) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    assert invoker.is_working_tree_dirty(working_directory) is False
    (working_directory / DIRTY_FILE_NAME).write_text(
        DIRTY_FILE_CONTENTS, encoding="utf-8"
    )
    assert invoker.is_working_tree_dirty(working_directory) is True


def test_git_status_command_uses_porcelain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    all_commands: list[list[str]] = []

    def fake_git_status(
        all_command_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals, all_keywords
        all_commands.append(list(all_command_tokens))
        return subprocess.CompletedProcess(
            args=list(all_command_tokens),
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(invoker, "review_git_status_runner", fake_git_status)
    invoker.is_working_tree_dirty(working_directory)
    assert all_commands == [[GIT_BINARY, GIT_STATUS_SUBCOMMAND, GIT_PORCELAIN_FLAG]]


def test_is_working_tree_dirty_nonzero_returncode_is_not_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")

    def fake_git_status(
        all_command_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals, all_keywords
        return subprocess.CompletedProcess(
            args=list(all_command_tokens),
            returncode=FIXTURE_GIT_STATUS_FAILURE_RETURNCODE,
            stdout="",
            stderr="fatal: not a git repository",
        )

    monkeypatch.setattr(invoker, "review_git_status_runner", fake_git_status)
    assert invoker.is_working_tree_dirty(working_directory) is True
