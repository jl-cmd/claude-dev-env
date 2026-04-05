"""Tests for code quality checks."""

import ast
import tempfile
from pathlib import Path

import pytest

from code_quality_checks import (
    check_function_length,
    check_nesting_depth,
    check_file_length,
)
from validator_base import Violation


GOOD_SHORT_FUNCTION = '''
def process(items):
    result = []
    for item in items:
        if item.active:
            result.append(item)
    return result
'''

BAD_LONG_FUNCTION = '''
def process(items):
    line1 = 1
    line2 = 2
    line3 = 3
    line4 = 4
    line5 = 5
    line6 = 6
    line7 = 7
    line8 = 8
    line9 = 9
    line10 = 10
    line11 = 11
    line12 = 12
    line13 = 13
    line14 = 14
    line15 = 15
    line16 = 16
    line17 = 17
    line18 = 18
    line19 = 19
    line20 = 20
    line21 = 21
    line22 = 22
    line23 = 23
    line24 = 24
    line25 = 25
    line26 = 26
    line27 = 27
    line28 = 28
    line29 = 29
    line30 = 30
    line31 = 31
    return line31
'''

GOOD_SHALLOW_NESTING = '''
def process(items):
    for item in items:
        if item.active:
            result.append(item)
    return result
'''

BAD_DEEP_NESTING = '''
def process(items):
    for item in items:
        if item.active:
            if item.valid:
                if item.enabled:
                    result.append(item)
    return result
'''


class TestFunctionLength:
    def test_short_function_passes(self) -> None:
        tree = ast.parse(GOOD_SHORT_FUNCTION)
        violations = check_function_length(tree, "test.py")
        assert violations == []

    def test_long_function_fails(self) -> None:
        tree = ast.parse(BAD_LONG_FUNCTION)
        violations = check_function_length(tree, "test.py")
        assert len(violations) == 1
        assert "30" in violations[0].message or "lines" in violations[0].message.lower()


class TestNestingDepth:
    def test_shallow_nesting_passes(self) -> None:
        tree = ast.parse(GOOD_SHALLOW_NESTING)
        violations = check_nesting_depth(tree, "test.py")
        assert violations == []

    def test_deep_nesting_fails(self) -> None:
        tree = ast.parse(BAD_DEEP_NESTING)
        violations = check_nesting_depth(tree, "test.py")
        assert len(violations) == 1
        assert "nesting" in violations[0].message.lower()


class TestFileLength:
    def test_short_file_passes(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
            temp_file.write("x = 1\n" * 100)
            temp_path = Path(temp_file.name)

        try:
            violations = check_file_length(temp_path)
            assert violations == []
        finally:
            temp_path.unlink()

    def test_long_file_fails(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
            temp_file.write("x = 1\n" * 450)
            temp_path = Path(temp_file.name)

        try:
            violations = check_file_length(temp_path)
            assert len(violations) == 1
            assert "400" in violations[0].message or "lines" in violations[0].message.lower()
        finally:
            temp_path.unlink()
