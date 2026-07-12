"""Tests for the blank-line auto-fixers and standalone invocation."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .python_style_checks import (
    check_blank_lines_between_functions,
    fix_file,
    fix_function_spacing,
)

GOOD_IMPORTS = """import os
import sys

def foo() -> None:
    pass
"""

GOOD_TWO_LINES_BETWEEN_FUNCTIONS = """def foo() -> None:
    pass


def bar() -> None:
    pass
"""

BAD_NO_LINE_BETWEEN_FUNCTIONS = """def foo() -> None:
    pass
def bar() -> None:
    pass
"""

BAD_ONE_LINE_BETWEEN_FUNCTIONS = """def foo() -> None:
    pass

def bar() -> None:
    pass
"""

BAD_THREE_LINES_BETWEEN_FUNCTIONS = """def foo() -> None:
    pass



def bar() -> None:
    pass
"""

DECORATED_NEXT_TWO_LINES = """def foo() -> None:
    pass


@decorator
def bar() -> None:
    pass
"""

ONE_BLANK_BEFORE_DECORATED = """def foo() -> None:
    pass

@decorator
def bar() -> None:
    pass
"""

FORM_FEED_BETWEEN_FUNCTIONS = "def foo():\n    pass\n\x0c\n\ndef bar():\n    pass\n"


class TestAutoFix:
    """Test auto-fix capabilities."""

    def test_fix_empty_line_after_decorator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-fix should remove blank line between decorator and function."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        code = """@decorator

def foo():
    pass
"""
        expected = """@decorator
def foo():
    pass
"""
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
        code = """def foo():
    pass



def bar():
    pass
"""
        expected = """def foo():
    pass


def bar():
    pass
"""
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
        code = """def foo():
    pass


def bar():
    pass
"""
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
        assert check_blank_lines_between_functions(FORM_FEED_BETWEEN_FUNCTIONS, "test.py") == []
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

    def test_ast_module_import_available(self) -> None:
        """The ast module the checker depends on parses a trivial module."""
        assert ast.parse("x = 1").body
