"""Tests for abbreviation detection."""

import ast
from pathlib import Path

import pytest

from abbreviation_checks import (
    check_single_letter_variables,
    validate_file,
)
from validator_base import Violation


GOOD_DESCRIPTIVE_NAMES = '''
def process_data(items):
    item_data = get_item()
    for file_path in files:
        result = process(file_path)
    return [item for item in items if item.active]
'''

BAD_SINGLE_LETTER_ASSIGNMENT = '''
def process():
    t = get_item()
    return t
'''

BAD_SINGLE_LETTER_LOOP = '''
def process(files):
    for f in files:
        print(f)
'''

BAD_SINGLE_LETTER_COMPREHENSION = '''
def process(items):
    return [x for x in items if x.active]
'''

ALLOWED_LOOP_COUNTERS = '''
def process(matrix):
    for i in range(10):
        for j in range(10):
            for k in range(10):
                matrix[i][j][k] = 0
'''


class TestSingleLetterVariables:
    def test_descriptive_names_pass(self) -> None:
        tree = ast.parse(GOOD_DESCRIPTIVE_NAMES)
        violations = check_single_letter_variables(tree, "test.py")
        assert violations == []

    def test_single_letter_assignment_fails(self) -> None:
        tree = ast.parse(BAD_SINGLE_LETTER_ASSIGNMENT)
        violations = check_single_letter_variables(tree, "test.py")
        assert len(violations) == 1
        assert "t" in violations[0].message

    def test_single_letter_loop_variable_fails(self) -> None:
        tree = ast.parse(BAD_SINGLE_LETTER_LOOP)
        violations = check_single_letter_variables(tree, "test.py")
        assert len(violations) == 1
        assert "f" in violations[0].message

    def test_single_letter_comprehension_fails(self) -> None:
        tree = ast.parse(BAD_SINGLE_LETTER_COMPREHENSION)
        violations = check_single_letter_variables(tree, "test.py")
        assert len(violations) == 1
        assert "x" in violations[0].message

    def test_loop_counters_ijk_allowed(self) -> None:
        tree = ast.parse(ALLOWED_LOOP_COUNTERS)
        violations = check_single_letter_variables(tree, "test.py")
        assert violations == []
