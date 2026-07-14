"""Behavioral tests for the verified-commit gate's directory-change resolution."""

import os

import pytest

from verified_commit_gate_parts.directory_resolution import (
    argument_tokens_after_verb,
    directory_change_target,
    expand_home_prefix,
    is_absolute_directory,
    resolve_against,
    split_option_value,
    value_after_option,
)


def test_split_option_value_splits_an_equals_form_option() -> None:
    assert split_option_value("--work-tree=/repo") == ("--work-tree", "/repo")


def test_split_option_value_returns_none_value_for_a_bare_option() -> None:
    assert split_option_value("-C") == ("-C", None)


def test_value_after_option_reads_the_next_token() -> None:
    assert value_after_option(["-C", "/repo", "commit"], 0) == "/repo"


def test_value_after_option_returns_none_at_the_end() -> None:
    assert value_after_option(["-C"], 0) is None


def test_expand_home_prefix_expands_a_leading_tilde(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "C:/fake-home")
    monkeypatch.setenv("USERPROFILE", "C:/fake-home")
    assert expand_home_prefix("~/repo") == os.path.expanduser("~/repo")


def test_is_absolute_directory_true_for_a_drive_path() -> None:
    assert is_absolute_directory("C:/repo")


def test_is_absolute_directory_false_for_a_relative_path() -> None:
    assert not is_absolute_directory("subdir")


def test_resolve_against_joins_a_relative_target() -> None:
    assert resolve_against("/session", "subdir") == os.path.join("/session", "subdir")


def test_resolve_against_replaces_with_an_absolute_target() -> None:
    assert resolve_against("/session", "/repo") == "/repo"


def test_argument_tokens_after_verb_stops_at_a_separator() -> None:
    command_text = "cd subdir; git commit"
    match_end = command_text.index("cd") + len("cd")
    assert argument_tokens_after_verb(command_text, match_end) == ["subdir"]


def test_directory_change_target_reads_the_destination() -> None:
    command_text = "cd /repo"
    match_end = command_text.index("cd") + len("cd")
    assert directory_change_target(command_text, match_end) == "/repo"


def test_directory_change_target_none_for_a_bare_change() -> None:
    command_text = "cd && git commit"
    match_end = command_text.index("cd") + len("cd")
    assert directory_change_target(command_text, match_end) is None
