"""Type safety checks validator.

Implements:
- Check 39: Missing type hints on functions
- Check 40: Any type usage
"""

import ast
import sys
from pathlib import Path
from typing import List

from .validator_base import Violation


def check_missing_type_hints(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_") and node.name != "__init__":
                continue

            if node.returns is None:
                violations.append(
                    Violation(
                        filename,
                        node.lineno,
                        f"Function '{node.name}' missing return type annotation",
                    )
                )

            for arg in node.args.args:
                if arg.arg == "self" or arg.arg == "cls":
                    continue
                if arg.annotation is None:
                    violations.append(
                        Violation(
                            filename,
                            node.lineno,
                            f"Parameter '{arg.arg}' in '{node.name}' missing type annotation",
                        )
                    )

    return violations


def check_any_type(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "Any":
            violations.append(
                Violation(
                    filename,
                    node.lineno,
                    "Any type used - use specific type or generic",
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

    violations.extend(check_missing_type_hints(tree, filename))
    violations.extend(check_any_type(tree, filename))

    return violations


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: type_safety_checks.py <file1.py> [file2.py ...]", file=sys.stderr)
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
