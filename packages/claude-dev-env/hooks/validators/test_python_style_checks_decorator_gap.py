"""Tests for multi-line decorator gap detection and repair.

These cover the case where a decorator spans several source lines: the
validator measures the gap from the decorator's last line to the def, and
the fixer removes any blank line that falls in that gap.
"""

import ast

from .python_style_checks import (
    check_no_empty_line_after_decorators,
    fix_empty_lines_after_decorators,
)

MULTILINE_DECORATOR_NO_BLANK = """@parametrize(
    "value",
    [1, 2, 3],
)
def check_values() -> None:
    pass
"""

MULTILINE_DECORATOR_WITH_BLANK = """@parametrize(
    "value",
    [1, 2, 3],
)

def check_values() -> None:
    pass
"""

SINGLE_DECORATOR_NO_BLANK = """@decorator
def foo() -> None:
    pass
"""

SINGLE_DECORATOR_WITH_BLANK = """@decorator

def foo() -> None:
    pass
"""

STACKED_DECORATORS_WITH_INNER_BLANK = """@first

@second
def foo() -> None:
    pass
"""

STACKED_DECORATORS_NO_BLANK = """@first
@second
def foo() -> None:
    pass
"""


class TestMultilineDecoratorValidator:
    """Validate gap detection for decorators spanning several lines."""

    def test_multiline_decorator_no_blank_valid(self) -> None:
        """A multi-line decorator directly above its def passes."""
        violations = check_no_empty_line_after_decorators(MULTILINE_DECORATOR_NO_BLANK, "test.py")
        assert violations == []

    def test_multiline_decorator_with_blank_fails(self) -> None:
        """A blank line after a multi-line decorator is flagged."""
        violations = check_no_empty_line_after_decorators(MULTILINE_DECORATOR_WITH_BLANK, "test.py")
        assert len(violations) == 1
        assert "decorator" in violations[0].message.lower()

    def test_single_decorator_no_blank_valid(self) -> None:
        """A single-line decorator directly above its def passes."""
        violations = check_no_empty_line_after_decorators(SINGLE_DECORATOR_NO_BLANK, "test.py")
        assert violations == []

    def test_single_decorator_with_blank_fails(self) -> None:
        """A blank line after a single-line decorator is flagged."""
        violations = check_no_empty_line_after_decorators(SINGLE_DECORATOR_WITH_BLANK, "test.py")
        assert len(violations) == 1
        assert violations[0].line == 1
        assert "decorator" in violations[0].message.lower()


class TestMultilineDecoratorFixer:
    """Validate blank-line removal around decorators spanning several lines."""

    def test_fixer_removes_multiline_decorator_gap(self) -> None:
        """The fixer removes the blank between a multi-line decorator and its def."""
        fixed_source = fix_empty_lines_after_decorators(MULTILINE_DECORATOR_WITH_BLANK)
        ast.parse(fixed_source)
        assert check_no_empty_line_after_decorators(fixed_source, "test.py") == []
        assert fixed_source == MULTILINE_DECORATOR_NO_BLANK

    def test_fixer_removes_single_decorator_gap(self) -> None:
        """The fixer removes the blank after a single-line decorator."""
        fixed_source = fix_empty_lines_after_decorators(SINGLE_DECORATOR_WITH_BLANK)
        assert fixed_source == SINGLE_DECORATOR_NO_BLANK

    def test_fixer_removes_blank_between_stacked_decorators(self) -> None:
        """The fixer removes a blank line separating stacked decorators."""
        fixed_source = fix_empty_lines_after_decorators(STACKED_DECORATORS_WITH_INNER_BLANK)
        ast.parse(fixed_source)
        assert fixed_source == STACKED_DECORATORS_NO_BLANK

    def test_fixer_leaves_clean_multiline_decorator_untouched(self) -> None:
        """A multi-line decorator with no gap survives the fixer unchanged."""
        fixed_source = fix_empty_lines_after_decorators(MULTILINE_DECORATOR_NO_BLANK)
        assert fixed_source == MULTILINE_DECORATOR_NO_BLANK

    def test_fixer_is_idempotent(self) -> None:
        """Applying the fixer twice matches applying it once."""
        once = fix_empty_lines_after_decorators(MULTILINE_DECORATOR_WITH_BLANK)
        twice = fix_empty_lines_after_decorators(once)
        assert twice == once

    def test_fixer_returns_source_unchanged_on_syntax_error(self) -> None:
        """Unparseable source is returned unchanged rather than corrupted."""
        broken_source = "@decorator\n\ndef foo(\n"
        assert fix_empty_lines_after_decorators(broken_source) == broken_source
