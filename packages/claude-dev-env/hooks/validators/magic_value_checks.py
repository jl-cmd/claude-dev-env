"""Magic value detection validator.

Implements check 7: No hardcoded magic values.
Use named constants instead of magic numbers.

Note: Only checks for magic numbers. Magic string detection is not implemented.
"""

import ast
import sys
from pathlib import Path
from typing import List, Set

from validator_base import Violation


ALLOWED_NUMBERS: Set[int] = frozenset({-1, 0, 1, 2, 100})


def check_magic_values(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    constant_names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constant_names.add(target.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int) and node.value not in ALLOWED_NUMBERS:
                if not _is_in_constant_definition(node, tree):
                    violations.append(
                        Violation(
                            filename,
                            node.lineno,
                            f"Magic number {node.value} - use named constant",
                        )
                    )

    return violations


def _is_in_constant_definition(node: ast.Constant, tree: ast.AST) -> bool:
    for parent in ast.walk(tree):
        if isinstance(parent, ast.Assign):
            for target in parent.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    if parent.value is node:
                        return True
    return False


def validate_file(file_path: Path) -> List[Violation]:
    filename = str(file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as error:
        return [Violation(filename, 0, f"Error: {error}")]

    return check_magic_values(tree, filename)


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
