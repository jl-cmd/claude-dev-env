"""Python style checks using AST-based validation.

Implements four style checks:
1. Imports at top of file
2. No empty lines after decorators
3. Single empty line between functions
4. View functions end with _view suffix
"""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


# Constants
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
    """Check that all imports are at the top of the file.

    Catches two violations:
    1. Module-level imports after non-import statements
    2. Imports inside functions/classes (inline imports)

    Args:
        tree: AST tree to check
        filename: Name of file being checked

    Returns:
        List of violations found
    """
    violations: List[Violation] = []

    # Check 1: Module-level imports must be at top
    if isinstance(tree, ast.Module):
        seen_non_import = False
        for child in tree.body:
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                if seen_non_import:
                    violations.append(
                        Violation(
                            filename,
                            child.lineno,
                            "Import statement must be at top of file",
                        )
                    )
            elif isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant):
                # Allow docstrings at top
                if isinstance(child.value.value, str):
                    continue
                seen_non_import = True
            else:
                seen_non_import = True

    # Check 2: No imports inside functions or methods
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    violations.append(
                        Violation(
                            filename,
                            child.lineno,
                            "Import inside function - move to top of file",
                        )
                    )

    return violations


def check_no_empty_line_after_decorators(source: str, filename: str) -> List[Violation]:
    """Check that decorators have no empty line before function.

    Args:
        source: Source code as string
        filename: Name of file being checked

    Returns:
        List of violations found
    """
    violations: List[Violation] = []
    lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list:
            # Get last decorator line
            last_decorator_line = max(d.lineno for d in node.decorator_list)
            function_line = node.lineno

            # Check if there's an empty line between decorator and function
            if function_line - last_decorator_line > 1:
                violations.append(
                    Violation(
                        filename,
                        last_decorator_line,
                        "No empty line allowed between decorator and function",
                    )
                )

    return violations


def check_single_empty_line_between_functions(
    source: str, filename: str
) -> List[Violation]:
    """Check that functions have exactly one empty line between them.

    Args:
        source: Source code as string
        filename: Name of file being checked

    Returns:
        List of violations found
    """
    violations: List[Violation] = []
    lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    # Get all top-level function definitions
    functions = [
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    # Filter to only top-level functions (not nested)
    if isinstance(tree, ast.Module):
        top_level_functions = [
            node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    else:
        top_level_functions = []

    # Sort by line number
    top_level_functions.sort(key=lambda f: f.lineno)

    # Check spacing between consecutive functions
    for i in range(len(top_level_functions) - 1):
        current_func = top_level_functions[i]
        next_func = top_level_functions[i + 1]

        # Find last line of current function
        current_end = current_func.end_lineno
        next_start = next_func.lineno

        if current_end is not None:
            # Calculate empty lines between functions
            empty_lines = next_start - current_end - 1

            if empty_lines != 1:
                violations.append(
                    Violation(
                        filename,
                        current_end,
                        f"Expected 1 empty line between functions, found {empty_lines}",
                    )
                )

    return violations


def check_view_function_naming(tree: ast.AST, filename: str) -> List[Violation]:
    """Check that view functions end with _view suffix.

    Only applies to functions in views.py that have 'request' as first parameter.

    Args:
        tree: AST tree to check
        filename: Name of file being checked

    Returns:
        List of violations found
    """
    violations: List[Violation] = []

    # Only check files named views.py
    if not filename.endswith(VIEWS_FILENAME):
        return violations

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check if first parameter is 'request'
            if node.args.args and node.args.args[0].arg == REQUEST_PARAM:
                # Check if function name ends with _view
                if not node.name.endswith(VIEW_SUFFIX):
                    violations.append(
                        Violation(
                            filename,
                            node.lineno,
                            f"View function '{node.name}' must end with '{VIEW_SUFFIX}'",
                        )
                    )

    return violations


def fix_empty_lines_after_decorators(source: str) -> str:
    """Remove empty lines between decorators and function definitions.

    Args:
        source: Source code as string

    Returns:
        Fixed source code
    """
    lines = source.splitlines(keepends=True)
    result_lines: List[str] = []
    skip_next_blank = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("@"):
            skip_next_blank = True
            result_lines.append(line)
        elif skip_next_blank and stripped == "":
            continue
        else:
            skip_next_blank = False
            result_lines.append(line)

    return "".join(result_lines)


def fix_multiple_blank_lines(source: str) -> str:
    """Collapse multiple blank lines between functions to single blank line.

    Args:
        source: Source code as string

    Returns:
        Fixed source code
    """
    lines = source.splitlines(keepends=True)
    result_lines: List[str] = []
    blank_count = 0

    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 1:
                result_lines.append(line)
        else:
            blank_count = 0
            result_lines.append(line)

    return "".join(result_lines)


def fix_file(file_path: Path) -> bool:
    """Apply all safe fixes to a file.

    Args:
        file_path: Path to file to fix

    Returns:
        True if any fixes were applied, False otherwise
    """
    try:
        original = file_path.read_text(encoding="utf-8")
    except Exception:
        return False

    fixed = original
    fixed = fix_empty_lines_after_decorators(fixed)
    fixed = fix_multiple_blank_lines(fixed)

    if fixed != original:
        file_path.write_text(fixed, encoding="utf-8")
        return True

    return False


def validate_file(file_path: Path) -> List[Violation]:
    """Validate a Python file with all style checks.

    Args:
        file_path: Path to Python file to validate

    Returns:
        List of all violations found
    """
    violations: List[Violation] = []
    filename = str(file_path)

    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as e:
        violations.append(Violation(filename, 0, f"Error reading file: {e}"))
        return violations

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        violations.append(
            Violation(filename, e.lineno or 0, f"Syntax error: {e.msg}")
        )
        return violations

    # Run all checks
    violations.extend(check_imports_at_top(tree, filename))
    violations.extend(check_no_empty_line_after_decorators(source, filename))
    violations.extend(check_single_empty_line_between_functions(source, filename))
    violations.extend(check_view_function_naming(tree, filename))

    return violations


def main() -> int:
    """Main entry point for command-line usage.

    Returns:
        Exit code: 0 if all files pass, 1 if violations found
    """
    if len(sys.argv) < 2:
        print("Usage: python_style_checks.py <file1.py> [file2.py ...]", file=sys.stderr)
        return 1

    all_violations: List[Violation] = []

    for file_arg in sys.argv[1:]:
        file_path = Path(file_arg)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            return 1

        violations = validate_file(file_path)
        all_violations.extend(violations)

    # Print all violations
    for violation in all_violations:
        print(violation)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
