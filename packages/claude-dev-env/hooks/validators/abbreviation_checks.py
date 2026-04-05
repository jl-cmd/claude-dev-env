"""Abbreviation detection validator.

Implements check 5: No single-letter variable names (except i, j, k for loop counters).

Detects:
- Single-letter assignments: t = value
- Single-letter loop variables: for f in files
- Single-letter comprehension variables: [x for x in items]
"""

import ast
import sys
from pathlib import Path
from typing import List, Set

from validator_base import Violation


ALLOWED_SINGLE_LETTERS: Set[str] = frozenset({"i", "j", "k", "_"})


def check_single_letter_variables(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if len(node.id) == 1 and node.id not in ALLOWED_SINGLE_LETTERS:
                violations.append(
                    Violation(
                        filename,
                        node.lineno,
                        f"Single-letter variable '{node.id}' - use descriptive name",
                    )
                )

    return violations


def validate_file(file_path: Path) -> List[Violation]:
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

    violations.extend(check_single_letter_variables(tree, filename))
    return violations


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: abbreviation_checks.py <file1.py> [file2.py ...]", file=sys.stderr)
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
