"""Tests for Python style checks."""

import ast
import tempfile
from pathlib import Path
from typing import List

import pytest

from .python_style_checks import (
    Violation,
    check_imports_at_top,
    check_no_empty_line_after_decorators,
    check_single_empty_line_between_functions,
    check_view_function_naming,
    fix_file,
    validate_file,
)


# Test data: Code samples
GOOD_IMPORTS = '''import os
import sys
from typing import List

def foo() -> None:
    pass
'''

BAD_IMPORTS_AFTER_CODE = '''def foo() -> None:
    pass

import os
'''

BAD_IMPORTS_AFTER_CONSTANT = '''MY_CONSTANT = 42

import os
'''

GOOD_DECORATOR_NO_BLANK = '''@decorator
def foo() -> None:
    pass
'''

BAD_DECORATOR_WITH_BLANK = '''@decorator

def foo() -> None:
    pass
'''

GOOD_SINGLE_LINE_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass

def bar() -> None:
    pass
'''

BAD_NO_LINE_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass
def bar() -> None:
    pass
'''

BAD_MULTIPLE_LINES_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass


def bar() -> None:
    pass
'''

GOOD_VIEW_NAMING = '''def user_profile_view(request):
    pass

def get_tasks_view(request, user_id):
    pass
'''

BAD_VIEW_NAMING = '''def user_profile(request):
    pass

def getTasks(request, user_id):
    pass
'''

GOOD_NON_VIEW_FUNCTION = '''def helper_function(data):
    pass

def process_data(items):
    pass
'''

# Async function test samples
ASYNC_GOOD_DECORATOR_NO_BLANK = '''import asyncio

@asyncio.coroutine
async def foo() -> None:
    await asyncio.sleep(0)
'''

ASYNC_BAD_DECORATOR_WITH_BLANK = '''import asyncio

@asyncio.coroutine

async def foo() -> None:
    await asyncio.sleep(0)
'''

ASYNC_GOOD_SINGLE_LINE_BETWEEN = '''import asyncio

async def foo() -> None:
    await asyncio.sleep(0)

async def bar() -> None:
    await asyncio.sleep(0)
'''

ASYNC_BAD_MULTIPLE_LINES_BETWEEN = '''import asyncio

async def foo() -> None:
    await asyncio.sleep(0)


async def bar() -> None:
    await asyncio.sleep(0)
'''

ASYNC_GOOD_VIEW_NAMING = '''from django.http import HttpRequest, HttpResponse

async def user_profile_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("profile")

async def get_tasks_view(request: HttpRequest, user_id: int) -> HttpResponse:
    return HttpResponse("tasks")
'''

ASYNC_BAD_VIEW_NAMING = '''from django.http import HttpRequest, HttpResponse

async def user_profile(request: HttpRequest) -> HttpResponse:
    return HttpResponse("profile")

async def getTasks(request: HttpRequest, user_id: int) -> HttpResponse:
    return HttpResponse("tasks")
'''

ASYNC_BAD_INLINE_IMPORT = '''import asyncio

async def foo() -> None:
    import json
    await asyncio.sleep(0)
'''


class TestImportsAtTop:
    """Test import positioning validation."""

    def test_imports_at_top_valid(self) -> None:
        """All imports at top should pass."""
        tree = ast.parse(GOOD_IMPORTS)
        violations = check_imports_at_top(tree, "test.py")
        assert violations == []

    def test_import_after_function(self) -> None:
        """Import after function should fail."""
        tree = ast.parse(BAD_IMPORTS_AFTER_CODE)
        violations = check_imports_at_top(tree, "test.py")
        assert len(violations) == 1
        assert violations[0].line == 4
        assert "import" in violations[0].message.lower()

    def test_import_after_constant(self) -> None:
        """Import after constant should fail."""
        tree = ast.parse(BAD_IMPORTS_AFTER_CONSTANT)
        violations = check_imports_at_top(tree, "test.py")
        assert len(violations) == 1
        assert violations[0].line == 3

    def test_async_inline_import_fails(self) -> None:
        """Import inside async function should fail."""
        tree = ast.parse(ASYNC_BAD_INLINE_IMPORT)
        violations = check_imports_at_top(tree, "test.py")
        assert len(violations) == 1
        assert "inside function" in violations[0].message.lower()


class TestNoEmptyLineAfterDecorators:
    """Test decorator spacing validation."""

    def test_no_blank_line_valid(self) -> None:
        """Decorator directly above function should pass."""
        violations = check_no_empty_line_after_decorators(
            GOOD_DECORATOR_NO_BLANK, "test.py"
        )
        assert violations == []

    def test_blank_line_after_decorator_fails(self) -> None:
        """Blank line after decorator should fail."""
        violations = check_no_empty_line_after_decorators(
            BAD_DECORATOR_WITH_BLANK, "test.py"
        )
        assert len(violations) == 1
        assert violations[0].line == 1
        assert "decorator" in violations[0].message.lower()

    def test_async_no_blank_line_valid(self) -> None:
        """Decorator directly above async function should pass."""
        violations = check_no_empty_line_after_decorators(
            ASYNC_GOOD_DECORATOR_NO_BLANK, "test.py"
        )
        assert violations == []

    def test_async_blank_line_after_decorator_fails(self) -> None:
        """Blank line after decorator on async function should fail."""
        violations = check_no_empty_line_after_decorators(
            ASYNC_BAD_DECORATOR_WITH_BLANK, "test.py"
        )
        assert len(violations) == 1
        assert violations[0].line == 3
        assert "decorator" in violations[0].message.lower()


class TestSingleEmptyLineBetweenFunctions:
    """Test function spacing validation."""

    def test_single_line_valid(self) -> None:
        """Exactly one blank line should pass."""
        violations = check_single_empty_line_between_functions(
            GOOD_SINGLE_LINE_BETWEEN_FUNCTIONS, "test.py"
        )
        assert violations == []

    def test_no_line_between_functions_fails(self) -> None:
        """No blank line should fail."""
        violations = check_single_empty_line_between_functions(
            BAD_NO_LINE_BETWEEN_FUNCTIONS, "test.py"
        )
        assert len(violations) == 1
        assert "empty line" in violations[0].message.lower()

    def test_multiple_lines_between_functions_fails(self) -> None:
        """Multiple blank lines should fail."""
        violations = check_single_empty_line_between_functions(
            BAD_MULTIPLE_LINES_BETWEEN_FUNCTIONS, "test.py"
        )
        assert len(violations) == 1
        assert "empty line" in violations[0].message.lower()

    def test_async_single_line_valid(self) -> None:
        """Exactly one blank line between async functions should pass."""
        violations = check_single_empty_line_between_functions(
            ASYNC_GOOD_SINGLE_LINE_BETWEEN, "test.py"
        )
        assert violations == []

    def test_async_multiple_lines_fails(self) -> None:
        """Multiple blank lines between async functions should fail."""
        violations = check_single_empty_line_between_functions(
            ASYNC_BAD_MULTIPLE_LINES_BETWEEN, "test.py"
        )
        assert len(violations) == 1
        assert "empty line" in violations[0].message.lower()


class TestViewFunctionNaming:
    """Test view function naming validation."""

    def test_view_functions_named_correctly(self) -> None:
        """View functions ending with _view should pass."""
        tree = ast.parse(GOOD_VIEW_NAMING)
        violations = check_view_function_naming(tree, "views.py")
        assert violations == []

    def test_view_functions_without_suffix_fail(self) -> None:
        """View functions not ending with _view should fail."""
        tree = ast.parse(BAD_VIEW_NAMING)
        violations = check_view_function_naming(tree, "views.py")
        assert len(violations) == 2
        assert all("_view" in v.message for v in violations)

    def test_non_view_file_ignored(self) -> None:
        """Non-views.py files should be ignored."""
        tree = ast.parse(BAD_VIEW_NAMING)
        violations = check_view_function_naming(tree, "utils.py")
        assert violations == []

    def test_non_request_function_ignored(self) -> None:
        """Functions without request parameter should be ignored."""
        tree = ast.parse(GOOD_NON_VIEW_FUNCTION)
        violations = check_view_function_naming(tree, "views.py")
        assert violations == []

    def test_async_view_functions_named_correctly(self) -> None:
        """Async view functions ending with _view should pass."""
        tree = ast.parse(ASYNC_GOOD_VIEW_NAMING)
        violations = check_view_function_naming(tree, "views.py")
        assert violations == []

    def test_async_view_functions_without_suffix_fail(self) -> None:
        """Async view functions not ending with _view should fail."""
        tree = ast.parse(ASYNC_BAD_VIEW_NAMING)
        violations = check_view_function_naming(tree, "views.py")
        assert len(violations) == 2
        assert all("_view" in v.message for v in violations)


class TestValidateFile:
    """Test file validation integration."""

    def test_valid_file_passes(self) -> None:
        """File with no violations should pass."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(GOOD_IMPORTS)
            f.flush()
            temp_path = Path(f.name)

        try:
            violations = validate_file(temp_path)
            assert violations == []
        finally:
            temp_path.unlink()

    def test_invalid_file_returns_violations(self) -> None:
        """File with violations should return them."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(BAD_IMPORTS_AFTER_CODE)
            f.flush()
            temp_path = Path(f.name)

        try:
            violations = validate_file(temp_path)
            assert len(violations) > 0
            assert all(isinstance(v, Violation) for v in violations)
        finally:
            temp_path.unlink()

    def test_syntax_error_returns_violation(self) -> None:
        """File with syntax error should return violation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def foo(\n")  # Invalid syntax
            f.flush()
            temp_path = Path(f.name)

        try:
            violations = validate_file(temp_path)
            assert len(violations) == 1
            assert "syntax error" in violations[0].message.lower()
        finally:
            temp_path.unlink()


class TestViolationClass:
    """Test Violation dataclass."""

    def test_violation_creation(self) -> None:
        """Violation should store file, line, message."""
        v = Violation("test.py", 42, "Test message")
        assert v.file == "test.py"
        assert v.line == 42
        assert v.message == "Test message"

    def test_violation_str_format(self) -> None:
        """Violation should format as file:line: message."""
        v = Violation("test.py", 42, "Test message")
        assert str(v) == "test.py:42: Test message"


class TestAutoFix:
    """Test auto-fix capabilities."""

    def test_fix_empty_line_after_decorator(self) -> None:
        """Auto-fix should remove blank line between decorator and function."""
        code = '''@decorator

def foo():
    pass
'''
        expected = '''@decorator
def foo():
    pass
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
            temp_file.write(code)
            temp_path = Path(temp_file.name)

        try:
            fixed = fix_file(temp_path)
            assert fixed is True
            result = temp_path.read_text()
            assert result.strip() == expected.strip()
        finally:
            temp_path.unlink()

    def test_fix_multiple_blank_lines_between_functions(self) -> None:
        """Auto-fix should collapse multiple blank lines to single."""
        code = '''def foo():
    pass


def bar():
    pass
'''
        expected = '''def foo():
    pass

def bar():
    pass
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
            temp_file.write(code)
            temp_path = Path(temp_file.name)

        try:
            fixed = fix_file(temp_path)
            assert fixed is True
            result = temp_path.read_text()
            assert result.strip() == expected.strip()
        finally:
            temp_path.unlink()

    def test_no_fix_needed_returns_false(self) -> None:
        """Auto-fix should return False when no fixes needed."""
        code = '''def foo():
    pass

def bar():
    pass
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
            temp_file.write(code)
            temp_path = Path(temp_file.name)

        try:
            fixed = fix_file(temp_path)
            assert fixed is False
        finally:
            temp_path.unlink()
