"""Tests for Python style checks."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .python_style_checks import (
    Violation,
    check_blank_lines_between_functions,
    check_imports_at_top,
    check_no_empty_line_after_decorators,
    check_view_function_naming,
    fix_file,
    fix_function_spacing,
    validate_file,
)

GOOD_IMPORTS = '''import os
import sys

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

ASYNC_BAD_INLINE_IMPORT = '''import asyncio

async def foo() -> None:
    import json
    await asyncio.sleep(0)
'''

GOOD_DECORATOR_NO_BLANK = '''@decorator
def foo() -> None:
    pass
'''

BAD_DECORATOR_WITH_BLANK = '''@decorator

def foo() -> None:
    pass
'''

ASYNC_BAD_DECORATOR_WITH_BLANK = '''import asyncio

@asyncio.coroutine

async def foo() -> None:
    pass
'''

GOOD_TWO_LINES_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass


def bar() -> None:
    pass
'''

BAD_NO_LINE_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass
def bar() -> None:
    pass
'''

BAD_ONE_LINE_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass

def bar() -> None:
    pass
'''

BAD_THREE_LINES_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass



def bar() -> None:
    pass
'''

ASYNC_GOOD_TWO_LINES_BETWEEN = '''async def foo() -> None:
    pass


async def bar() -> None:
    pass
'''

GOOD_VIEW_NAMING = '''def user_profile_view(request):
    pass

def get_tasks_view(request, user_id):
    pass
'''

BAD_VIEW_NAMING = '''def user_profile(request):
    pass

def get_tasks(request, user_id):
    pass
'''

GOOD_NON_VIEW_FUNCTION = '''def helper_function(payload):
    pass

def process_records(items):
    pass
'''

ASYNC_BAD_VIEW_NAMING = '''async def user_profile(request):
    pass

async def get_tasks(request, user_id):
    pass
'''

DECORATED_NEXT_TWO_LINES = '''def foo() -> None:
    pass


@decorator
def bar() -> None:
    pass
'''

ONE_BLANK_BEFORE_DECORATED = '''def foo() -> None:
    pass

@decorator
def bar() -> None:
    pass
'''

COMMENT_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass


# helper comment
def bar() -> None:
    pass
'''

CLASS_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass


class Middle:
    pass


def bar() -> None:
    pass
'''

MODULE_STATEMENT_BETWEEN_FUNCTIONS = '''def foo() -> None:
    pass


answer = 42


def bar() -> None:
    pass
'''

FORM_FEED_BETWEEN_FUNCTIONS = "def foo():\n    pass\n\x0c\n\ndef bar():\n    pass\n"


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

    def test_async_blank_line_after_decorator_fails(self) -> None:
        """Blank line after decorator on async function should fail."""
        violations = check_no_empty_line_after_decorators(
            ASYNC_BAD_DECORATOR_WITH_BLANK, "test.py"
        )
        assert len(violations) == 1
        assert violations[0].line == 3
        assert "decorator" in violations[0].message.lower()


class TestBlankLinesBetweenFunctions:
    """Test function spacing validation."""

    def test_two_lines_valid(self) -> None:
        """Exactly two blank lines should pass."""
        violations = check_blank_lines_between_functions(
            GOOD_TWO_LINES_BETWEEN_FUNCTIONS, "test.py"
        )
        assert violations == []

    def test_no_line_between_functions_fails(self) -> None:
        """No blank line should fail."""
        violations = check_blank_lines_between_functions(
            BAD_NO_LINE_BETWEEN_FUNCTIONS, "test.py"
        )
        assert len(violations) == 1
        assert "empty line" in violations[0].message.lower()

    def test_one_line_between_functions_fails(self) -> None:
        """A single blank line should fail under the two-line rule."""
        violations = check_blank_lines_between_functions(
            BAD_ONE_LINE_BETWEEN_FUNCTIONS, "test.py"
        )
        assert len(violations) == 1
        assert "empty line" in violations[0].message.lower()

    def test_three_lines_between_functions_fails(self) -> None:
        """Three or more blank lines should fail."""
        violations = check_blank_lines_between_functions(
            BAD_THREE_LINES_BETWEEN_FUNCTIONS, "test.py"
        )
        assert len(violations) == 1
        assert "empty line" in violations[0].message.lower()

    def test_async_two_lines_valid(self) -> None:
        """Exactly two blank lines between async functions should pass."""
        violations = check_blank_lines_between_functions(
            ASYNC_GOOD_TWO_LINES_BETWEEN, "test.py"
        )
        assert violations == []

    def test_decorated_next_function_two_lines_valid(self) -> None:
        """Two blanks before a decorated next function should pass."""
        violations = check_blank_lines_between_functions(
            DECORATED_NEXT_TWO_LINES, "test.py"
        )
        assert violations == []

    def test_comment_between_functions_passes(self) -> None:
        """A comment in the gap leaves the surrounding functions unflagged."""
        violations = check_blank_lines_between_functions(
            COMMENT_BETWEEN_FUNCTIONS, "test.py"
        )
        assert violations == []

    def test_class_between_functions_passes(self) -> None:
        """An interposed class leaves the surrounding functions unflagged."""
        violations = check_blank_lines_between_functions(
            CLASS_BETWEEN_FUNCTIONS, "test.py"
        )
        assert violations == []

    def test_module_statement_between_functions_passes(self) -> None:
        """A module-level statement in the gap leaves the pair unflagged."""
        violations = check_blank_lines_between_functions(
            MODULE_STATEMENT_BETWEEN_FUNCTIONS, "test.py"
        )
        assert violations == []


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
        assert all("_view" in each_violation.message for each_violation in violations)

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

    def test_async_view_functions_without_suffix_fail(self) -> None:
        """Async view functions not ending with _view should fail."""
        tree = ast.parse(ASYNC_BAD_VIEW_NAMING)
        violations = check_view_function_naming(tree, "views.py")
        assert len(violations) == 2
        assert all("_view" in each_violation.message for each_violation in violations)


class TestValidateFile:
    """Test file validation integration."""

    def test_valid_file_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """File with no violations should pass."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        temp_path = tmp_path / "valid_module.py"
        temp_path.write_text(GOOD_IMPORTS, encoding="utf-8")
        violations = validate_file(temp_path)
        assert violations == []

    def test_invalid_file_returns_violations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """File with violations should return them."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        temp_path = tmp_path / "invalid_module.py"
        temp_path.write_text(BAD_IMPORTS_AFTER_CODE, encoding="utf-8")
        violations = validate_file(temp_path)
        assert len(violations) > 0
        assert all(isinstance(each_violation, Violation) for each_violation in violations)

    def test_syntax_error_returns_violation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """File with syntax error should return violation."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        temp_path = tmp_path / "broken_module.py"
        temp_path.write_text("def foo(\n", encoding="utf-8")
        violations = validate_file(temp_path)
        assert len(violations) == 1
        assert "syntax error" in violations[0].message.lower()


class TestViolationClass:
    """Test Violation dataclass."""

    def test_violation_creation(self) -> None:
        """Violation should store file, line, message."""
        violation = Violation("test.py", 42, "Test message")
        assert violation.file == "test.py"
        assert violation.line == 42
        assert violation.message == "Test message"

    def test_violation_str_format(self) -> None:
        """Violation should format as file:line: message."""
        violation = Violation("test.py", 42, "Test message")
        assert str(violation) == "test.py:42: Test message"


class TestAutoFix:
    """Test auto-fix capabilities."""

    def test_fix_empty_line_after_decorator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-fix should remove blank line between decorator and function."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        code = '''@decorator

def foo():
    pass
'''
        expected = '''@decorator
def foo():
    pass
'''
        temp_path = tmp_path / "decorator_module.py"
        temp_path.write_text(code, encoding="utf-8")
        fixed = fix_file(temp_path)
        assert fixed is True
        result_text = temp_path.read_text()
        assert result_text.strip() == expected.strip()

    def test_fix_collapses_three_blank_lines_to_two(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-fix should collapse three or more blank lines down to two."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
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
        temp_path = tmp_path / "spacing_module.py"
        temp_path.write_text(code, encoding="utf-8")
        fixed = fix_file(temp_path)
        assert fixed is True
        result_text = temp_path.read_text()
        assert result_text.strip() == expected.strip()

    def test_fix_inserts_missing_blank_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-fix should insert blank lines for under-spaced functions."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        temp_path = tmp_path / "underspaced_module.py"
        temp_path.write_text(BAD_ONE_LINE_BETWEEN_FUNCTIONS, encoding="utf-8")
        fixed = fix_file(temp_path)
        assert fixed is True
        assert temp_path.read_text() == GOOD_TWO_LINES_BETWEEN_FUNCTIONS

    def test_no_fix_needed_returns_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-fix should return False when the file already uses two blank lines."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        code = '''def foo():
    pass


def bar():
    pass
'''
        temp_path = tmp_path / "clean_module.py"
        temp_path.write_text(code, encoding="utf-8")
        fixed = fix_file(temp_path)
        assert fixed is False

    def test_form_feed_gap_stays_check_clean_after_fix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A form feed in a blank gap converges without corrupting the file."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        assert (
            check_blank_lines_between_functions(FORM_FEED_BETWEEN_FUNCTIONS, "test.py")
            == []
        )
        temp_path = tmp_path / "form_feed_module.py"
        temp_path.write_text(FORM_FEED_BETWEEN_FUNCTIONS, encoding="utf-8")
        fix_file(temp_path)
        fixed_text = temp_path.read_text()
        assert check_blank_lines_between_functions(fixed_text, "test.py") == []
        assert fix_file(temp_path) is False


class TestFixFunctionSpacing:
    """Test blank-line normalization between top-level functions."""

    def test_inserts_two_blank_lines_when_adjacent(self) -> None:
        """Adjacent functions gain exactly two blank lines."""
        fixed_source = fix_function_spacing(BAD_NO_LINE_BETWEEN_FUNCTIONS)
        assert fixed_source == GOOD_TWO_LINES_BETWEEN_FUNCTIONS

    def test_inserts_second_blank_line_when_one(self) -> None:
        """A single blank line grows to exactly two."""
        fixed_source = fix_function_spacing(BAD_ONE_LINE_BETWEEN_FUNCTIONS)
        assert fixed_source == GOOD_TWO_LINES_BETWEEN_FUNCTIONS

    def test_collapses_three_blank_lines_to_two(self) -> None:
        """Three blank lines collapse to exactly two."""
        fixed_source = fix_function_spacing(BAD_THREE_LINES_BETWEEN_FUNCTIONS)
        assert fixed_source == GOOD_TWO_LINES_BETWEEN_FUNCTIONS

    def test_normalizes_before_decorated_function(self) -> None:
        """Blank lines before a decorated function normalize to two."""
        fixed_source = fix_function_spacing(ONE_BLANK_BEFORE_DECORATED)
        assert fixed_source == DECORATED_NEXT_TWO_LINES


class TestDirectInvocation:
    """Test running the checker as a standalone script."""

    def test_direct_invocation_resolves_hooks_constants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Direct invocation bootstraps hooks_constants without PYTHONPATH."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        script_path = Path(__file__).resolve().parent / "python_style_checks.py"
        target_path = tmp_path / "clean_sample.py"
        target_path.write_text(GOOD_IMPORTS, encoding="utf-8")
        scrubbed_environment = dict(os.environ)
        scrubbed_environment.pop("PYTHONPATH", None)
        completed_process = subprocess.run(
            [sys.executable, "-S", str(script_path), str(target_path)],
            capture_output=True,
            text=True,
            env=scrubbed_environment,
        )
        assert "ModuleNotFoundError" not in completed_process.stderr
        assert completed_process.returncode == 0
