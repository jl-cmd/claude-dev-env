"""Useless test detection validator.

Implements check 12: No useless tests.
Tests must verify behavior, not existence or constant values.
"""

import ast
import sys
from pathlib import Path
from typing import List

from .validator_base import Violation


def check_useless_tests(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            for child in ast.walk(node):
                if isinstance(child, ast.Assert):
                    if _is_callable_check(child):
                        violations.append(
                            Violation(filename, child.lineno, "Useless test: callable() check doesn't verify behavior")
                        )
                    elif _is_hasattr_check(child):
                        violations.append(
                            Violation(filename, child.lineno, "Useless test: hasattr() check doesn't verify behavior")
                        )
                    elif _is_constant_value_check(child):
                        violations.append(
                            Violation(filename, child.lineno, "Useless test: testing constant value doesn't verify behavior")
                        )

    return violations


def _is_callable_check(node: ast.Assert) -> bool:
    if isinstance(node.test, ast.Call):
        if isinstance(node.test.func, ast.Name) and node.test.func.id == "callable":
            return True
    return False


def _is_hasattr_check(node: ast.Assert) -> bool:
    if isinstance(node.test, ast.Call):
        if isinstance(node.test.func, ast.Name) and node.test.func.id == "hasattr":
            return True
    return False


def _is_constant_value_check(node: ast.Assert) -> bool:
    if isinstance(node.test, ast.Compare):
        if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
            left = node.test.left
            right = node.test.comparators[0] if node.test.comparators else None
            if isinstance(left, ast.Name) and left.id.isupper():
                if isinstance(right, ast.Constant) and isinstance(right.value, str):
                    return True
    return False


def validate_file(file_path: Path) -> List[Violation]:
    filename = str(file_path)
    if "test" not in filename.lower():
        return []

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as error:
        return [Violation(filename, 0, f"Error: {error}")]

    return check_useless_tests(tree, filename)


def main() -> int:
    if len(sys.argv) < 2:
        return 1

    all_violations: List[Violation] = []
    for file_arg in sys.argv[1:]:
        all_violations.extend(validate_file(Path(file_arg)))

    for violation in all_violations:
        print(violation)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
