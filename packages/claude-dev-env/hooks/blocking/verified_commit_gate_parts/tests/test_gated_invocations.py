"""Behavioral tests for gated git-invocation directory resolution."""

import os

from verified_commit_gate_parts.gated_invocations import (
    gated_invocation_directory,
    gated_repo_directories,
)


def test_gated_invocation_directory_true_for_commit_in_subcommand_position() -> None:
    is_gated, repo_directory = gated_invocation_directory(["commit", "-m", "x"])
    assert is_gated
    assert repo_directory is None


def test_gated_invocation_directory_false_for_commit_as_an_argument() -> None:
    is_gated, _ = gated_invocation_directory(["stash", "push"])
    assert not is_gated


def test_gated_invocation_directory_reads_the_dash_c_directory() -> None:
    is_gated, repo_directory = gated_invocation_directory(["-C", "/repo", "commit"])
    assert is_gated
    assert repo_directory == "/repo"


def test_gated_repo_directories_finds_a_bare_commit() -> None:
    assert gated_repo_directories("git commit -m x", "/session") == ["/session"]


def test_gated_repo_directories_ignores_a_quoted_prose_mention() -> None:
    assert gated_repo_directories('echo "Next: git commit"', "/session") == []


def test_gated_repo_directories_follows_a_preceding_cd() -> None:
    assert gated_repo_directories("cd subdir && git commit -m x", "/session") == [
        os.path.join("/session", "subdir")
    ]


def test_gated_repo_directories_honors_a_dash_c_flag() -> None:
    assert gated_repo_directories("git -C /repo commit -m x", "/session") == ["/repo"]


def test_gated_repo_directories_empty_for_a_non_gated_subcommand() -> None:
    assert gated_repo_directories("git status", "/session") == []
