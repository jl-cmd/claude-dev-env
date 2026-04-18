"""Tests for Python anti-pattern detection."""

import ast

import pytest

from .python_antipattern_checks import (
    check_mutable_default_args,
    check_bare_except,
    check_print_in_production,
)
from .validator_base import Violation


GOOD_NONE_DEFAULT = '''
def process(items=None):
    if items is None:
        items = []
    return items
'''

BAD_MUTABLE_DEFAULT = '''
def process(items=[]):
    return items
'''

BAD_DICT_DEFAULT = '''
def process(config={}):
    return config
'''

GOOD_SPECIFIC_EXCEPT = '''
def process():
    try:
        do_work()
    except ValueError:
        handle_error()
'''

BAD_BARE_EXCEPT = '''
def process():
    try:
        do_work()
    except:
        handle_error()
'''

GOOD_LOGGING = '''
import logging

def process():
    logging.info("Processing")
'''

BAD_PRINT = '''
def process():
    print("Debug info")
'''

TEST_FILE_WITH_PRINT = '''
def test_something():
    print("Test output")
    assert True
'''


class TestMutableDefaultArgs:
    def test_none_default_passes(self) -> None:
        tree = ast.parse(GOOD_NONE_DEFAULT)
        violations = check_mutable_default_args(tree, "test.py")
        assert violations == []

    def test_list_default_fails(self) -> None:
        tree = ast.parse(BAD_MUTABLE_DEFAULT)
        violations = check_mutable_default_args(tree, "test.py")
        assert len(violations) == 1
        assert "mutable" in violations[0].message.lower()

    def test_dict_default_fails(self) -> None:
        tree = ast.parse(BAD_DICT_DEFAULT)
        violations = check_mutable_default_args(tree, "test.py")
        assert len(violations) == 1


class TestBareExcept:
    def test_specific_except_passes(self) -> None:
        tree = ast.parse(GOOD_SPECIFIC_EXCEPT)
        violations = check_bare_except(tree, "test.py")
        assert violations == []

    def test_bare_except_fails(self) -> None:
        tree = ast.parse(BAD_BARE_EXCEPT)
        violations = check_bare_except(tree, "test.py")
        assert len(violations) == 1
        assert "bare" in violations[0].message.lower() or "except" in violations[0].message.lower()


class TestPrintInProduction:
    def test_logging_passes(self) -> None:
        tree = ast.parse(GOOD_LOGGING)
        violations = check_print_in_production(tree, "utils.py")
        assert violations == []

    def test_print_fails(self) -> None:
        tree = ast.parse(BAD_PRINT)
        violations = check_print_in_production(tree, "utils.py")
        assert len(violations) == 1
        assert "print" in violations[0].message.lower()

    def test_print_in_test_file_allowed(self) -> None:
        tree = ast.parse(TEST_FILE_WITH_PRINT)
        violations = check_print_in_production(tree, "test_utils.py")
        assert violations == []
