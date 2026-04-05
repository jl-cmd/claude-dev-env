"""Tests for TODO/FIXME detection."""

import pytest

from todo_checks import check_untracked_todos
from validator_base import Violation


GOOD_TODO_WITH_ISSUE = '''
def process():
    pass
'''

BAD_TODO_WITHOUT_ISSUE = '''
def process():
    pass
'''


class TestUntrackedTodos:
    def test_no_todo_passes(self) -> None:
        violations = check_untracked_todos(GOOD_TODO_WITH_ISSUE, "test.py")
        assert violations == []

    def test_todo_without_issue_fails(self) -> None:
        code = "# TODO: fix this later\ndef foo(): pass"
        violations = check_untracked_todos(code, "test.py")
        assert len(violations) == 1
        assert "TODO" in violations[0].message

    def test_todo_with_issue_passes(self) -> None:
        code = "# TODO #123: fix this later\ndef foo(): pass"
        violations = check_untracked_todos(code, "test.py")
        assert violations == []

    def test_fixme_without_issue_fails(self) -> None:
        code = "# FIXME: broken\ndef foo(): pass"
        violations = check_untracked_todos(code, "test.py")
        assert len(violations) == 1
