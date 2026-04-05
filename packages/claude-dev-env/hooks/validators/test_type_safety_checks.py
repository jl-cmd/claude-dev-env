"""Tests for type safety checks."""

import ast

import pytest

from type_safety_checks import (
    check_missing_type_hints,
    check_any_type,
)
from validator_base import Violation


GOOD_FULLY_TYPED = '''
def process(items: list[str]) -> int:
    return len(items)
'''

BAD_NO_RETURN_TYPE = '''
def process(items: list[str]):
    return len(items)
'''

BAD_NO_PARAM_TYPE = '''
def process(items) -> int:
    return len(items)
'''

GOOD_NO_ANY = '''
from typing import List

def process(items: List[str]) -> int:
    return len(items)
'''

BAD_ANY_TYPE = '''
from typing import Any

def process(items: Any) -> int:
    return len(items)
'''

BAD_ANY_RETURN = '''
from typing import Any, List

def process(items: List[str]) -> Any:
    return items[0]
'''


class TestMissingTypeHints:
    def test_fully_typed_passes(self) -> None:
        tree = ast.parse(GOOD_FULLY_TYPED)
        violations = check_missing_type_hints(tree, "test.py")
        assert violations == []

    def test_missing_return_type_fails(self) -> None:
        tree = ast.parse(BAD_NO_RETURN_TYPE)
        violations = check_missing_type_hints(tree, "test.py")
        assert len(violations) == 1
        assert "return" in violations[0].message.lower()

    def test_missing_param_type_fails(self) -> None:
        tree = ast.parse(BAD_NO_PARAM_TYPE)
        violations = check_missing_type_hints(tree, "test.py")
        assert len(violations) == 1
        assert "items" in violations[0].message or "parameter" in violations[0].message.lower()


class TestAnyType:
    def test_no_any_passes(self) -> None:
        tree = ast.parse(GOOD_NO_ANY)
        violations = check_any_type(tree, "test.py")
        assert violations == []

    def test_any_param_fails(self) -> None:
        tree = ast.parse(BAD_ANY_TYPE)
        violations = check_any_type(tree, "test.py")
        assert len(violations) == 1
        assert "Any" in violations[0].message

    def test_any_return_fails(self) -> None:
        tree = ast.parse(BAD_ANY_RETURN)
        violations = check_any_type(tree, "test.py")
        assert len(violations) == 1
