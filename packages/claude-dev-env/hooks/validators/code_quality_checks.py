"""Code quality checks validator.

Implements:
- Check 30: Function too long (max 30 lines)
- Check 31: Nesting too deep (max 2 levels)
- Check 32: File too long (max 400 lines)
"""

import ast
import sys
from pathlib import Path
from typing import List

from validator_base import Violation


MAX_FUNCTION_LINES = 30
MAX_NESTING_DEPTH = 2
MAX_FILE_LINES = 400


def check_function_length(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.end_lineno and node.lineno:
                length = node.end_lineno - node.lineno + 1
                if length > MAX_FUNCTION_LINES:
                    violations.append(
                        Violation(
                            filename,
                            node.lineno,
                            f"Function '{node.name}' is {length} lines (max {MAX_FUNCTION_LINES})",
                        )
                    )

    return violations


def check_nesting_depth(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            max_depth = _get_max_nesting_depth(node, 0)
            if max_depth > MAX_NESTING_DEPTH:
                violations.append(
                    Violation(
                        filename,
                        node.lineno,
                        f"Function '{node.name}' has nesting depth {max_depth} (max {MAX_NESTING_DEPTH})",
                    )
                )

    return violations


def _get_max_nesting_depth(node: ast.AST, current_depth: int) -> int:
    max_depth = current_depth

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            child_depth = _get_max_nesting_depth(child, current_depth + 1)
            max_depth = max(max_depth, child_depth)
        else:
            child_depth = _get_max_nesting_depth(child, current_depth)
            max_depth = max(max_depth, child_depth)

    return max_depth


def check_file_length(file_path: Path) -> List[Violation]:
    violations: List[Violation] = []
    filename = str(file_path)

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception as error:
        return [Violation(filename, 0, f"Error reading file: {error}")]

    if len(lines) > MAX_FILE_LINES:
        violations.append(
            Violation(
                filename,
                1,
                f"File is {len(lines)} lines (max {MAX_FILE_LINES}) - consider splitting",
            )
        )

    return violations


def validate_file(file_path: Path) -> List[Violation]:
    violations: List[Violation] = []
    filename = str(file_path)

    violations.extend(check_file_length(file_path))

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as error:
        return violations + [Violation(filename, 0, f"Error: {error}")]

    violations.extend(check_function_length(tree, filename))
    violations.extend(check_nesting_depth(tree, filename))

    return violations


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: code_quality_checks.py <file1.py> [file2.py ...]", file=sys.stderr)
        return 1

    all_violations: List[Violation] = []

    for file_arg in sys.argv[1:]:
        file_path = Path(file_arg)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            return 1
        all_violations.extend(validate_file(file_path))

    for violation in all_violations:
        print(violation)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
