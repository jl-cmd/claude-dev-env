"""Python style checks using AST-based validation.

Implements four style checks:
1. Imports at top of file
2. No empty lines after decorators
3. Two empty lines between top-level functions
4. View functions end with _view suffix
"""

import ast
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

try:
    from hooks_constants.python_style_checks_constants import (
        EXPECTED_BLANK_LINES_BETWEEN_FUNCTIONS,
        MINIMUM_ARGUMENT_COUNT,
    )
except ModuleNotFoundError:
    _hooks_directory = str(Path(__file__).resolve().parent.parent)
    if _hooks_directory not in sys.path:
        sys.path.insert(0, _hooks_directory)
    from hooks_constants.python_style_checks_constants import (
        EXPECTED_BLANK_LINES_BETWEEN_FUNCTIONS,
        MINIMUM_ARGUMENT_COUNT,
    )

try:
    from validators.python_style_helpers import (
        FunctionNode,
        blank_line_for_source,
        function_start_line,
        gap_is_blank_only,
        iter_function_definitions,
        real_newline_lines,
        top_level_functions,
    )
except ModuleNotFoundError:
    if _hooks_directory not in sys.path:
        sys.path.insert(0, _hooks_directory)
    from validators.python_style_helpers import (
        FunctionNode,
        blank_line_for_source,
        function_start_line,
        gap_is_blank_only,
        iter_function_definitions,
        real_newline_lines,
        top_level_functions,
    )

logger = logging.getLogger(__name__)

VIEW_SUFFIX = "_view"
REQUEST_PARAM = "request"
VIEWS_FILENAME = "views.py"


@dataclass
class Violation:
    """Represents a style violation."""

    file: str
    line: int
    message: str

    def __str__(self) -> str:
        """Format as file:line: message."""
        return f"{self.file}:{self.line}: {self.message}"


def check_imports_at_top(tree: ast.AST, filename: str) -> List[Violation]:
    """Check that all imports sit at the top of the file.

    Flags module-level imports that follow other statements and imports
    nested inside function or method bodies.
    """
    violations: List[Violation] = []
    violations.extend(_check_module_level_import_order(tree, filename))
    violations.extend(_check_no_inline_imports(tree, filename))
    return violations


def _is_import_statement(statement: ast.stmt) -> bool:
    """Return True when the statement is an import or from-import."""
    return isinstance(statement, (ast.Import, ast.ImportFrom))


def _is_docstring_statement(statement: ast.stmt) -> bool:
    """Return True when the statement is a string-literal docstring."""
    if not isinstance(statement, ast.Expr):
        return False
    literal = statement.value
    return isinstance(literal, ast.Constant) and isinstance(literal.value, str)


def _check_module_level_import_order(tree: ast.AST, filename: str) -> List[Violation]:
    """Flag module-level imports that appear after other statements."""
    if not isinstance(tree, ast.Module):
        return []
    violations: List[Violation] = []
    has_seen_non_import = False
    for each_statement in tree.body:
        is_import = _is_import_statement(each_statement)
        if is_import and has_seen_non_import:
            violations.append(
                Violation(
                    filename,
                    each_statement.lineno,
                    "Import statement must be at top of file",
                )
            )
        if not is_import and not _is_docstring_statement(each_statement):
            has_seen_non_import = True
    return violations


def _check_no_inline_imports(tree: ast.AST, filename: str) -> List[Violation]:
    """Flag import statements located inside function or method bodies."""
    violations: List[Violation] = []
    for each_function_node in iter_function_definitions(tree):
        violations.extend(_inline_imports_in(each_function_node, filename))
    return violations


def _inline_imports_in(function_node: FunctionNode, filename: str) -> List[Violation]:
    """Return violations for imports nested inside a single function."""
    violations: List[Violation] = []
    for each_descendant in ast.walk(function_node):
        if isinstance(each_descendant, (ast.Import, ast.ImportFrom)):
            violations.append(
                Violation(
                    filename,
                    each_descendant.lineno,
                    "Import inside function - move to top of file",
                )
            )
    return violations


def check_no_empty_line_after_decorators(source: str, filename: str) -> List[Violation]:
    """Check that no empty line separates a decorator from its function."""
    violations: List[Violation] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations
    for each_function_node in iter_function_definitions(tree):
        violation = _decorator_gap_violation(each_function_node, filename)
        if violation is not None:
            violations.append(violation)
    return violations


def _decorator_gap_violation(
    function_node: FunctionNode, filename: str
) -> Optional[Violation]:
    """Return a violation when an empty line separates a decorator from its function."""
    if not function_node.decorator_list:
        return None
    last_decorator_line = max(
        each_decorator.end_lineno or each_decorator.lineno
        for each_decorator in function_node.decorator_list
    )
    if function_node.lineno - last_decorator_line <= 1:
        return None
    return Violation(
        filename,
        last_decorator_line,
        "No empty line allowed between decorator and function",
    )


def check_blank_lines_between_functions(source: str, filename: str) -> List[Violation]:
    """Check that consecutive top-level functions carry the expected blank gap."""
    violations: List[Violation] = []
    source_lines = real_newline_lines(source)
    ordered_functions = top_level_functions(source)
    for each_current_function, each_next_function in zip(
        ordered_functions, ordered_functions[1:]
    ):
        violation = _spacing_violation(
            each_current_function, each_next_function, source_lines, filename
        )
        if violation is not None:
            violations.append(violation)
    return violations


def _spacing_violation(
    current_function: FunctionNode,
    next_function: FunctionNode,
    source_lines: List[str],
    filename: str,
) -> Optional[Violation]:
    """Return a violation when two functions hold the wrong blank-line count.

    A run of purely empty lines is measured; a run holding any other content
    is skipped, matching the fixer so a flagged file can be normalized.
    """
    current_end = current_function.end_lineno
    if current_end is None:
        return None
    next_start = function_start_line(next_function)
    gap_lines = source_lines[current_end : next_start - 1]
    if not gap_is_blank_only(gap_lines):
        return None
    blank_line_count = len(gap_lines)
    if blank_line_count == EXPECTED_BLANK_LINES_BETWEEN_FUNCTIONS:
        return None
    return Violation(
        filename,
        current_end,
        f"Expected {EXPECTED_BLANK_LINES_BETWEEN_FUNCTIONS} empty lines "
        f"between functions, found {blank_line_count}",
    )


def check_view_function_naming(tree: ast.AST, filename: str) -> List[Violation]:
    """Check that request-handling functions in views.py end with _view."""
    if not filename.endswith(VIEWS_FILENAME):
        return []
    violations: List[Violation] = []
    for each_function_node in iter_function_definitions(tree):
        if _is_misnamed_view(each_function_node):
            violations.append(
                Violation(
                    filename,
                    each_function_node.lineno,
                    f"View function '{each_function_node.name}' must end with '{VIEW_SUFFIX}'",
                )
            )
    return violations


def _is_misnamed_view(function_node: FunctionNode) -> bool:
    """Return True when a request handler is missing the _view suffix."""
    arguments = function_node.args.args
    if not arguments:
        return False
    if arguments[0].arg != REQUEST_PARAM:
        return False
    return not function_node.name.endswith(VIEW_SUFFIX)


def _decorator_span_line_numbers(decorators: List[ast.expr]) -> Set[int]:
    """Return every source line a decorator expression occupies."""
    occupied_lines: Set[int] = set()
    for each_decorator in decorators:
        end_line = each_decorator.end_lineno or each_decorator.lineno
        occupied_lines.update(range(each_decorator.lineno, end_line + 1))
    return occupied_lines


def _blank_gap_lines_for_function(
    function_node: FunctionNode, source_lines: List[str]
) -> Set[int]:
    """Return blank line numbers between one function's decorators and its def."""
    decorators = function_node.decorator_list
    if not decorators:
        return set()
    occupied_lines = _decorator_span_line_numbers(decorators)
    first_decorator_line = min(
        each_decorator.lineno for each_decorator in decorators
    )
    return {
        each_line_number
        for each_line_number in range(first_decorator_line, function_node.lineno)
        if each_line_number not in occupied_lines
        and source_lines[each_line_number - 1].strip() == ""
    }


def fix_empty_lines_after_decorators(source: str) -> str:
    """Remove empty lines between decorators and their function definitions.

    Blank lines separating stacked decorators, and blank lines between the
    last line of a multi-line decorator and the def, are both removed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    source_lines = real_newline_lines(source)
    blank_line_numbers: Set[int] = set()
    for each_function_node in iter_function_definitions(tree):
        blank_line_numbers |= _blank_gap_lines_for_function(
            each_function_node, source_lines
        )
    if not blank_line_numbers:
        return source
    return "".join(
        each_line
        for each_line_number, each_line in enumerate(source_lines, start=1)
        if each_line_number not in blank_line_numbers
    )


def _normalized_gap(all_gap_lines: List[str], blank_line: str) -> List[str]:
    """Return the between-function gap normalized to the expected blank count.

    A gap that is entirely blank becomes exactly the expected number of blank
    lines. A gap that holds any non-blank line stays untouched so no comment,
    class, or statement in it is lost.
    """
    if not gap_is_blank_only(all_gap_lines):
        return all_gap_lines
    return [blank_line] * EXPECTED_BLANK_LINES_BETWEEN_FUNCTIONS


def fix_function_spacing(source: str) -> str:
    """Normalize blank lines between top-level functions to exactly two."""
    functions = top_level_functions(source)
    if len(functions) <= 1:
        return source
    source_lines = real_newline_lines(source)
    blank_line = blank_line_for_source(source)
    previous_end_line = functions[0].end_lineno
    if previous_end_line is None:
        return source
    rebuilt: List[str] = list(source_lines[:previous_end_line])
    for each_next_function in functions[1:]:
        next_start_line = function_start_line(each_next_function)
        gap_lines = source_lines[previous_end_line : next_start_line - 1]
        rebuilt.extend(_normalized_gap(gap_lines, blank_line))
        next_end_line = each_next_function.end_lineno
        if next_end_line is None:
            return source
        rebuilt.extend(source_lines[next_start_line - 1 : next_end_line])
        previous_end_line = next_end_line
    rebuilt.extend(source_lines[previous_end_line:])
    return "".join(rebuilt)


def fix_file(file_path: Path) -> bool:
    """Apply the safe blank-line fixes and report whether the file changed.

    Path.read_text() normalizes every line ending to \\n before either fix
    below inspects the text.
    """
    try:
        original = file_path.read_text(encoding="utf-8")
    except Exception:
        return False
    decorators_fixed = fix_empty_lines_after_decorators(original)
    blank_lines_fixed = fix_function_spacing(decorators_fixed)
    if blank_lines_fixed == original:
        return False
    file_path.write_text(blank_lines_fixed, encoding="utf-8")
    return True


def validate_file(file_path: Path) -> List[Violation]:
    """Validate a Python file against every style check."""
    violations: List[Violation] = []
    filename = str(file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as error:
        violations.append(Violation(filename, 0, f"Error reading file: {error}"))
        return violations
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        violations.append(
            Violation(filename, error.lineno or 0, f"Syntax error: {error.msg}")
        )
        return violations
    violations.extend(check_imports_at_top(tree, filename))
    violations.extend(check_no_empty_line_after_decorators(source, filename))
    violations.extend(check_blank_lines_between_functions(source, filename))
    violations.extend(check_view_function_naming(tree, filename))
    return violations


def main() -> int:
    """Run the style checks over the files named on the command line."""
    minimum_argument_count = MINIMUM_ARGUMENT_COUNT
    if len(sys.argv) < minimum_argument_count:
        logger.error("Usage: %s <file1.py> [file2.py ...]", Path(sys.argv[0]).name)
        return 1
    all_violations: List[Violation] = []
    for each_file_arg in sys.argv[1:]:
        file_path = Path(each_file_arg)
        if not file_path.exists():
            logger.error("File not found: %s", file_path)
            return 1
        all_violations.extend(validate_file(file_path))
    for each_violation in all_violations:
        logger.error("%s", each_violation)
    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
