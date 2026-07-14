"""Behavioral tests for the commit repository-path resolution helpers.

Covers reading the repository a commit command targets, so the staged PII scan
runs against the named path rather than the session working directory::

    git -C /a -C sub commit   ->  /a/sub   (multiple -C compose)
    git -C /a/b -C /c/d commit ->  /c/d    (a later absolute -C resets)
    cd "/my repo" && git commit ->  /my repo (quoted cd path, shlex-parsed)
    git commit                 ->  None     (runs in the session cwd)
"""

from __future__ import annotations

from pathlib import Path

from pii_prevention_blocker_parts.repository_resolution import (
    compose_command_working_directory,
    expand_user_directory,
    refusal_reason_for_unresolved_repository,
)


def test_single_absolute_dash_c_is_the_target() -> None:
    assert compose_command_working_directory("git -C /repo commit -m x") == "/repo"


def test_relative_dash_c_composes_onto_a_leading_absolute_dash_c() -> None:
    composed = compose_command_working_directory("git -C /a -C sub commit -m x")
    assert composed is not None
    assert Path(composed) == Path("/a") / "sub"


def test_later_absolute_dash_c_resets_the_composition() -> None:
    assert compose_command_working_directory("git -C /a/b -C /c/d commit -m x") == "/c/d"


def test_quoted_dash_c_with_spaces_is_read_whole() -> None:
    assert compose_command_working_directory('git -C "/my repo" commit -m x') == "/my repo"


def test_leading_cd_supplies_the_target_when_no_dash_c() -> None:
    assert compose_command_working_directory("cd /work/repo && git commit -m x") == "/work/repo"


def test_quoted_cd_path_with_spaces_is_read_whole() -> None:
    assert compose_command_working_directory('cd "/my repo" && git commit -m x') == "/my repo"


def test_plain_commit_names_no_target() -> None:
    assert compose_command_working_directory("git commit -m x") is None


def test_expand_user_directory_expands_tilde() -> None:
    expanded = expand_user_directory("~/repo")
    assert expanded is not None
    assert not expanded.startswith("~")
    assert Path(expanded).name == "repo"


def test_expand_user_directory_passes_none_through() -> None:
    assert expand_user_directory(None) is None


def test_refusal_names_the_attempted_path() -> None:
    reason = refusal_reason_for_unresolved_repository("/gone/repo")
    assert "repository root" in reason
    assert "/gone/repo" in reason


def test_refusal_names_the_session_cwd_when_no_path_given() -> None:
    reason = refusal_reason_for_unresolved_repository(None)
    assert "repository root" in reason
    assert "session working directory" in reason


def test_windows_git_exe_dash_c_is_the_target() -> None:
    assert (
        compose_command_working_directory(r'git.exe -C "/srv/repo" commit -m x')
        == "/srv/repo"
    )
