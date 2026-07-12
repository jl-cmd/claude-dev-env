"""Tests for the shared source-line and function-discovery helpers."""

import ast

from .python_style_helpers import (
    blank_line_for_source,
    function_start_line,
    gap_is_blank_only,
    iter_function_definitions,
    real_newline_lines,
    top_level_functions,
)

TWO_FUNCTIONS = """def foo() -> None:
    pass


def bar() -> None:
    pass
"""

DECORATED_FUNCTION = """@decorator
def decorated() -> None:
    pass
"""

CRLF_SOURCE = "def foo() -> None:\r\n    pass\r\n"


class TestIterFunctionDefinitions:
    """Discovery of every function definition in a tree."""

    def test_yields_each_function(self) -> None:
        """Every top-level function is yielded."""
        tree = ast.parse(TWO_FUNCTIONS)
        names = [each.name for each in iter_function_definitions(tree)]
        assert names == ["foo", "bar"]

    def test_yields_nested_functions(self) -> None:
        """A nested function is discovered alongside its enclosing function."""
        tree = ast.parse("def outer() -> None:\n    def inner() -> None:\n        pass\n")
        names = {each.name for each in iter_function_definitions(tree)}
        assert names == {"outer", "inner"}


class TestTopLevelFunctions:
    """Ordered listing of a module's top-level functions."""

    def test_returns_functions_in_line_order(self) -> None:
        """Top-level functions are returned ordered by line."""
        ordered = top_level_functions(TWO_FUNCTIONS)
        assert [each.name for each in ordered] == ["foo", "bar"]

    def test_ignores_nested_functions(self) -> None:
        """A function nested inside another is not top-level."""
        ordered = top_level_functions(
            "def outer() -> None:\n    def inner() -> None:\n        pass\n"
        )
        assert [each.name for each in ordered] == ["outer"]

    def test_syntax_error_returns_empty(self) -> None:
        """Unparseable source yields no functions."""
        assert top_level_functions("def foo(") == []


class TestFunctionStartLine:
    """First source line of a function, counting decorators."""

    def test_undecorated_uses_def_line(self) -> None:
        """An undecorated function starts on its def line."""
        function_node = top_level_functions(TWO_FUNCTIONS)[0]
        assert function_start_line(function_node) == 1

    def test_decorated_uses_first_decorator_line(self) -> None:
        """A decorated function starts on its first decorator line."""
        function_node = top_level_functions(DECORATED_FUNCTION)[0]
        assert function_start_line(function_node) == 1


class TestGapIsBlankOnly:
    """Whether a run of lines between functions is entirely blank."""

    def test_all_blank_lines_true(self) -> None:
        """A gap of blank lines reports blank-only."""
        assert gap_is_blank_only(["\n", "   \n", ""]) is True

    def test_non_blank_line_false(self) -> None:
        """A gap holding any content is not blank-only."""
        assert gap_is_blank_only(["\n", "# comment\n"]) is False


class TestRealNewlineLines:
    """Line splitting aligned with ast line numbers."""

    def test_splits_on_lf(self) -> None:
        """LF-separated source splits into its lines with endings kept."""
        assert real_newline_lines("a\nb\n") == ["a\n", "b\n"]

    def test_splits_on_crlf(self) -> None:
        """CRLF pairs count as a single line ending."""
        assert real_newline_lines("a\r\nb\r\n") == ["a\r\n", "b\r\n"]

    def test_form_feed_stays_in_line(self) -> None:
        """A form feed does not start a new line, matching ast line numbers."""
        assert real_newline_lines("a\x0cb\n") == ["a\x0cb\n"]

    def test_trailing_partial_line_kept(self) -> None:
        """A final line with no ending is preserved."""
        assert real_newline_lines("a\nb") == ["a\n", "b"]

    def test_empty_source_returns_no_lines(self) -> None:
        """Empty source yields an empty list of lines."""
        assert real_newline_lines("") == []


class TestBlankLineForSource:
    """Blank-line string matching the source newline convention."""

    def test_lf_source_returns_lf(self) -> None:
        """LF source yields an LF blank line."""
        assert blank_line_for_source("a\nb\n") == "\n"

    def test_crlf_source_returns_crlf(self) -> None:
        """CRLF source yields a CRLF blank line."""
        assert blank_line_for_source(CRLF_SOURCE) == "\r\n"
