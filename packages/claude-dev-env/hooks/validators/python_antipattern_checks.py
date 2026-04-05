"""Python anti-pattern detection validator.

Implements:
- Check 33: Mutable default arguments
- Check 34: Bare except clauses
- Check 35: Print in production code
"""

import ast
import sys
from pathlib import Path
from typing import List

from validator_base import Violation


def check_mutable_default_args(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    violations.append(
                        Violation(
                            filename,
                            node.lineno,
                            f"Mutable default argument in '{node.name}' - use None and initialize inside",
                        )
                    )

    return violations


def check_bare_except(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                violations.append(
                    Violation(
                        filename,
                        node.lineno,
                        "Bare except clause - specify exception type",
                    )
                )

    return violations


def check_print_in_production(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    if "test" in filename.lower():
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                violations.append(
                    Violation(
                        filename,
                        node.lineno,
                        "print() in production code - use logging instead",
                    )
                )

    return violations


def validate_file(file_path: Path) -> List[Violation]:
    violations: List[Violation] = []
    filename = str(file_path)

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as error:
        return [Violation(filename, 0, f"Error: {error}")]

    violations.extend(check_mutable_default_args(tree, filename))
    violations.extend(check_bare_except(tree, filename))
    violations.extend(check_print_in_production(tree, filename))

    return violations


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python_antipattern_checks.py <file1.py> [file2.py ...]", file=sys.stderr)
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
