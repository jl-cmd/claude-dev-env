"""Shared source-line and function-discovery helpers for the style checks.

These pure helpers underlie the style checks and the blank-line fixers:
splitting source into ast-aligned lines, locating function definitions, and
matching the source newline convention.
"""

import ast
from collections.abc import Iterator
from typing import Union

FunctionNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]


def iter_function_definitions(tree: ast.AST) -> Iterator[FunctionNode]:
    """Yield every function and async-function definition in the tree."""
    for each_node in ast.walk(tree):
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield each_node


def top_level_functions(source: str) -> list[FunctionNode]:
    """Return the module's top-level function definitions, ordered by line."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    if not isinstance(tree, ast.Module):
        return []
    functions: list[FunctionNode] = [
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    functions.sort(key=lambda function_node: function_node.lineno)
    return functions


def function_start_line(function_node: FunctionNode) -> int:
    """Return the first source line of a function, counting its decorators."""
    if not function_node.decorator_list:
        return function_node.lineno
    return min(each_decorator.lineno for each_decorator in function_node.decorator_list)


def gap_is_blank_only(all_gap_lines: list[str]) -> bool:
    """Return True when every line between two functions is blank."""
    return all(each_line.strip() == "" for each_line in all_gap_lines)


def blank_line_for_source(source: str) -> str:
    """Return the blank-line string matching the source newline convention.

    Path.read_text() normalizes disk newlines to \\n before this runs, so the
    CRLF branch serves an in-memory caller that builds a CRLF string directly.
    """
    if "\r\n" in source:
        return "\r\n"
    return "\n"


def _advance_past_newline(source: str, scan_index: int) -> int | None:
    """Return the index past a CR, LF, or CRLF at scan_index, or None.

    None marks a character that is not a line ending.
    """
    character = source[scan_index]
    if character == "\r":
        scan_index += 1
        if scan_index < len(source) and source[scan_index] == "\n":
            scan_index += 1
        return scan_index
    if character == "\n":
        return scan_index + 1
    return None


def real_newline_lines(source: str) -> list[str]:
    """Split source on CR, LF, and CRLF only, keeping each line ending.

    Line indices stay aligned with ast line numbers because the split
    ignores form feed and other control characters ast does not count.
    """
    lines: list[str] = []
    line_start = 0
    scan_index = 0
    total_length = len(source)
    while scan_index < total_length:
        line_end = _advance_past_newline(source, scan_index)
        if line_end is None:
            scan_index += 1
            continue
        scan_index = line_end
        lines.append(source[line_start:scan_index])
        line_start = scan_index
    if line_start < total_length:
        lines.append(source[line_start:])
    return lines
