"""Tests for useless test detection."""

import ast

import pytest

from .useless_test_checks import (
    check_useless_tests,
)
from .validator_base import Violation


GOOD_BEHAVIOR_TEST = '''
def test_calculate_total():
    result = calculate_total([10, 20, 30])
    assert result == 60
'''

BAD_CALLABLE_CHECK = '''
def test_function_exists():
    assert callable(process_data)
'''

BAD_EXISTENCE_CHECK = '''
def test_constant_exists():
    assert hasattr(module, "CONSTANT")
'''

BAD_CONSTANT_VALUE_TEST = '''
def test_constant_value():
    assert CACHE_DIR == "cache"
'''


class TestUselessTests:
    def test_behavior_test_passes(self) -> None:
        tree = ast.parse(GOOD_BEHAVIOR_TEST)
        violations = check_useless_tests(tree, "test_example.py")
        assert violations == []

    def test_callable_check_fails(self) -> None:
        tree = ast.parse(BAD_CALLABLE_CHECK)
        violations = check_useless_tests(tree, "test_example.py")
        assert len(violations) == 1
        assert "callable" in violations[0].message.lower()

    def test_existence_check_fails(self) -> None:
        tree = ast.parse(BAD_EXISTENCE_CHECK)
        violations = check_useless_tests(tree, "test_example.py")
        assert len(violations) == 1

    def test_constant_value_test_fails(self) -> None:
        tree = ast.parse(BAD_CONSTANT_VALUE_TEST)
        violations = check_useless_tests(tree, "test_example.py")
        assert len(violations) == 1
