"""Parse validator output lines into locations and identity keys."""

import ast
from collections import Counter
from typing import List

from .config import MESSAGE_PARTITION_INDEX
from .validator_result import ValidatorResult


def _record_one_function_span(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    name_prefix: str,
    name_by_line: dict[int, str],
) -> None:
    """Assign every line of one function to its qualified name, then recurse."""
    qualified_name = f"{name_prefix}{function_node.name}"
    last_line = function_node.end_lineno or function_node.lineno
    for each_line in range(function_node.lineno, last_line + 1):
        name_by_line[each_line] = qualified_name
    _record_function_spans(function_node, f"{qualified_name}.", name_by_line)


def _record_child_span(
    child_node: ast.AST, name_prefix: str, name_by_line: dict[int, str]
) -> None:
    """Route one child node to the span recorder that matches its kind."""
    if isinstance(child_node, ast.ClassDef):
        _record_function_spans(child_node, f"{name_prefix}{child_node.name}.", name_by_line)
        return
    if isinstance(child_node, ast.FunctionDef | ast.AsyncFunctionDef):
        _record_one_function_span(child_node, name_prefix, name_by_line)
        return
    _record_function_spans(child_node, name_prefix, name_by_line)


def _record_function_spans(
    parent_node: ast.AST, name_prefix: str, name_by_line: dict[int, str]
) -> None:
    """Assign each line inside a function to that function's qualified name.

    Inner functions overwrite the enclosing name, so a line resolves to its
    innermost function; a method resolves to ``Class.method``.

    Args:
        parent_node: The AST node whose children are walked.
        name_prefix: The dotted qualifier accumulated from enclosing scopes.
        name_by_line: The line-to-name map filled in place.
    """
    for each_child in ast.iter_child_nodes(parent_node):
        _record_child_span(each_child, name_prefix, name_by_line)


def _enclosing_function_name_by_line(content: str) -> dict[int, str]:
    """Map each source line to its innermost enclosing function's qualified name.

    ::

        def outer():             # lines 1-4 -> "outer"
            def inner():         # lines 2-3 -> "outer.inner"
                return None
            return inner
        log_start()              # line 5 -> "" (module scope)

    Args:
        content: The full source text to parse.

    Returns:
        A line-to-name map; a line outside every function has no entry, so a
        lookup yields the empty string for module scope. An unparseable source
        yields an empty map.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {}
    name_by_line: dict[int, str] = {}
    _record_function_spans(tree, "", name_by_line)
    return name_by_line


def _violation_line_number(output_line: str) -> int:
    """Return the source line a validator's location prefix names.

    ::

        /pkg/legacy_module.py:37: magic number    -> line number 37
        /pkg/legacy_module.py:37:5: F401 unused   -> line number 37
        a summary line with no file location      -> line number 0
        1 | import os  (ruff code frame)          -> line number 0

    The line is the first colon-delimited field that is all digits, with every
    later prefix field also all digits (the column) and every earlier field
    reading like a path — no pipes or quotes, though spaces are allowed so a
    spaced directory or file name still parses. A ruff code-frame line quoting
    source text carries a pipe or quote before any digits, so frame and
    summary noise resolves to 0.

    Args:
        output_line: One printed ``Violation`` line from a validator.

    Returns:
        The parsed line number, or 0 for a line with no ``file:line`` prefix.
    """
    prefix_fields = output_line.partition(": ")[0].split(":")
    for each_field_index, each_field in enumerate(prefix_fields):
        if not each_field.isdigit():
            continue
        return _line_number_when_prefix_is_a_location(prefix_fields, each_field_index)
    return 0


def _line_number_when_prefix_is_a_location(
    prefix_fields: List[str], digit_field_index: int
) -> int:
    """Return the digit field as a line number when its prefix reads ``path:line``.

    Args:
        prefix_fields: The colon-split fields of the text before the message.
        digit_field_index: The index of the first all-digit field.

    Returns:
        The line number, or 0 when the surrounding fields do not form a
        ``path:line[:col]`` location.
    """
    non_path_characters = ("|", '"')
    if digit_field_index == 0:
        return 0
    path_fields = prefix_fields[:digit_field_index]
    looks_like_a_path = not any(
        each_character in each_path_field
        for each_path_field in path_fields
        for each_character in non_path_characters
    )
    trailing_fields = prefix_fields[digit_field_index + 1 :]
    if looks_like_a_path and all(each_field.isdigit() for each_field in trailing_fields):
        return int(prefix_fields[digit_field_index])
    return 0


def _identity_scope(output_line: str, name_by_line: dict[int, str]) -> str:
    """Return the enclosing-function name a single violation line belongs to.

    Args:
        output_line: One printed ``Violation`` line from a validator.
        name_by_line: The line-to-name map for the content that produced it.

    Returns:
        The enclosing function's qualified name, or the empty string for a
        module-scope or unlocatable violation.
    """
    return name_by_line.get(_violation_line_number(output_line), "")


def _failed_results(all_results: List[ValidatorResult]) -> List[ValidatorResult]:
    """Return the results that fired — not passed and not skipped."""
    return [
        each_result
        for each_result in all_results
        if not each_result.passed and not each_result.skipped
    ]


ViolationIdentity = tuple[str, str, str]


def _violation_message(output_line: str) -> str:
    """Return the message text after the ``path:line[:col]: `` location prefix.

    Args:
        output_line: One located violation line from a validator.

    Returns:
        The text after the first colon-space separator.
    """
    return output_line.partition(": ")[MESSAGE_PARTITION_INDEX]


def _located_violation_lines(each_result: ValidatorResult) -> List[str]:
    """Return the result's output lines that carry a real ``file:line`` location.

    Ruff code frames, help hints, and ``Found N errors`` summaries carry no
    location, so they are dropped rather than classified.

    Args:
        each_result: The failing validator result to filter.

    Returns:
        The located violation lines in output order.
    """
    return [
        each_output_line
        for each_output_line in each_result.output.splitlines()
        if _violation_line_number(each_output_line) > 0
    ]


def _line_identity(
    validator_name: str, output_line: str, name_by_line: dict[int, str]
) -> ViolationIdentity:
    """Return one line's ``(validator, enclosing function, message)`` identity key.

    Args:
        validator_name: The name of the validator that printed the line.
        output_line: One located violation line.
        name_by_line: The line-to-name map for the content that produced it.

    Returns:
        The identity key for baseline comparison.
    """
    return (
        validator_name,
        _identity_scope(output_line, name_by_line),
        _violation_message(output_line),
    )


def _violation_identities(
    failed_results: List[ValidatorResult], content: str
) -> Counter[ViolationIdentity]:
    """Count each located violation line by its identity key.

    Keying on the enclosing function rather than the raw line number keeps a
    key stable when an edit shifts that function, and counting rather than set
    membership keeps a second violation of the same validator in the same
    function visible as new.

    Args:
        failed_results: The validator results that fired.
        content: The source text those results were produced against.

    Returns:
        The multiset of violation identity keys.
    """
    name_by_line = _enclosing_function_name_by_line(content)
    return Counter(
        _line_identity(each_result.name, each_output_line, name_by_line)
        for each_result in failed_results
        for each_output_line in _located_violation_lines(each_result)
    )
