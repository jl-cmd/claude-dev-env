"""Behavioral tests for the split directory-change-into-stamp matcher.

The matcher blocks a command that changes into the Claude home, then into a
relative ``code-review-stamps`` directory, then runs any further command, while
an unrelated second change or a benign command passes.
"""

from __future__ import annotations

from code_review_stamp_write_blocker_parts.split_directory_change_into_stamp import (
    changes_through_split_directory_into_stamp,
)

SPLIT_CHANGE_FORGE = "cd ~/.claude && cd code-review-stamps && echo x > f.json"
UNRELATED_SECOND_CHANGE = "cd ~/.claude && cd hooks && echo x > f.json"
PYTEST_RUN = "python -m pytest test_code_review_stamp_store.py"


def test_split_change_into_stamp_then_command_is_blocked() -> None:
    assert changes_through_split_directory_into_stamp(SPLIT_CHANGE_FORGE)


def test_unrelated_second_change_is_not_blocked() -> None:
    assert not changes_through_split_directory_into_stamp(UNRELATED_SECOND_CHANGE)


def test_pytest_run_is_not_blocked() -> None:
    assert not changes_through_split_directory_into_stamp(PYTEST_RUN)


def test_change_into_stamp_without_following_command_is_not_blocked() -> None:
    assert not changes_through_split_directory_into_stamp("cd ~/.claude && cd code-review-stamps")


def test_pushd_split_change_into_stamp_then_command_is_blocked() -> None:
    assert changes_through_split_directory_into_stamp(
        "pushd ~/.claude && pushd code-review-stamps && cp a b"
    )
