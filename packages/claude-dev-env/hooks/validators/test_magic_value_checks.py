"""Tests for magic value detection."""

import ast

import pytest

from magic_value_checks import (
    check_magic_values,
)
from validator_base import Violation


GOOD_NAMED_CONSTANTS = '''
API_TIMEOUT_MS = 5000
HASH_DELIMITER = "__"

def process():
    timeout = API_TIMEOUT_MS
    return f"key{HASH_DELIMITER}value"
'''

BAD_MAGIC_NUMBER = '''
def process():
    timeout = 5000
    return timeout
'''

ALLOWED_SMALL_NUMBERS = '''
def process():
    count = 0
    increment = 1
    doubled = count * 2
    return count + 1
'''

ALLOWED_EMPTY_STRING = '''
def process():
    result = ""
    return result
'''


class TestMagicValues:
    def test_named_constants_pass(self) -> None:
        tree = ast.parse(GOOD_NAMED_CONSTANTS)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_magic_number_fails(self) -> None:
        tree = ast.parse(BAD_MAGIC_NUMBER)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "5000" in violations[0].message

    def test_small_numbers_allowed(self) -> None:
        tree = ast.parse(ALLOWED_SMALL_NUMBERS)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_empty_string_allowed(self) -> None:
        tree = ast.parse(ALLOWED_EMPTY_STRING)
        violations = check_magic_values(tree, "test.py")
        assert violations == []
