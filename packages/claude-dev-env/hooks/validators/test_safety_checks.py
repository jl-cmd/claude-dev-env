#!/usr/bin/env python3
"""AST-based safety validators for test files and development scripts.

This module provides checks for:
1. No skip decorators in test files (tests must fail, not skip)
2. DEBUG guard in Django management commands (dev tools only for DEBUG mode)
"""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


SKIP_DECORATOR_NAMES = frozenset([
    "skip",
    "skipif",
    "skipunless",
])

SKIP_DECORATOR_MESSAGE = (
    "Skip decorator not allowed. Tests should fail if they can't run. "
    "Missing dependencies should make the test fail with a clear error."
)

DEBUG_CHECK_MESSAGE = (
    "Management command in management/commands/ must check settings.DEBUG. "
    "Dev tools should only run in DEBUG mode."
)


@dataclass(frozen=True)
class Violation:
    """Represents a code violation found by a validator."""

    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.message}"


def check_no_skip_decorators(code: str, filepath: str) -> List[Violation]:
    """Check that test files don't use skip decorators.

    Args:
        code: Python source code to check
        filepath: Path to the file being checked (for error reporting)

    Returns:
        List of violations found
    """
    violations: List[Violation] = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for decorator in node.decorator_list:
            decorator_name = _get_decorator_name(decorator)
            if decorator_name.lower() in SKIP_DECORATOR_NAMES:
                violations.append(
                    Violation(
                        file=filepath,
                        line=node.lineno,
                        message=SKIP_DECORATOR_MESSAGE,
                    )
                )

    return violations


def _get_decorator_name(decorator: ast.expr) -> str:
    """Extract the name from a decorator node.

    Handles both simple decorators (@skip) and attribute decorators
    (@pytest.mark.skip, @unittest.skip).

    Args:
        decorator: AST decorator node

    Returns:
        The decorator name (e.g., "skip", "skipif")
    """
    if isinstance(decorator, ast.Name):
        return decorator.id

    if isinstance(decorator, ast.Attribute):
        return decorator.attr

    if isinstance(decorator, ast.Call):
        if isinstance(decorator.func, ast.Name):
            return decorator.func.id
        if isinstance(decorator.func, ast.Attribute):
            return decorator.func.attr

    return ""


def check_debug_guard_in_dev_scripts(code: str, filepath: str) -> List[Violation]:
    """Check that Django management commands check settings.DEBUG.

    Only applies to files in management/commands/ directories.

    Args:
        code: Python source code to check
        filepath: Path to the file being checked

    Returns:
        List of violations found
    """
    violations: List[Violation] = []

    normalized_path = filepath.replace("\\", "/")
    if "management/commands/" not in normalized_path:
        return violations

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return violations

    has_command_class = False
    has_debug_check = False
    command_line = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if any(
                isinstance(base, ast.Name) and base.id == "BaseCommand"
                for base in node.bases
            ):
                has_command_class = True
                command_line = node.lineno

                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "handle":
                        if _has_debug_guard(item):
                            has_debug_check = True

    if has_command_class and not has_debug_check:
        violations.append(
            Violation(
                file=filepath,
                line=command_line,
                message=DEBUG_CHECK_MESSAGE,
            )
        )

    return violations


def _has_debug_guard(func: ast.FunctionDef) -> bool:
    """Check if a function has a settings.DEBUG guard at the start.

    Looks for patterns like:
    - if not settings.DEBUG: raise/return
    - if settings.DEBUG: ... else: raise/return

    Args:
        func: Function definition node to check

    Returns:
        True if function has proper DEBUG guard
    """
    if not func.body:
        return False

    for stmt in func.body[:5]:
        if isinstance(stmt, ast.If):
            test = stmt.test

            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                if _is_debug_check(test.operand):
                    return True

            if _is_debug_check(test) and stmt.orelse:
                return True

    return False


def _is_debug_check(node: ast.expr) -> bool:
    """Check if a node is a settings.DEBUG check.

    Args:
        node: AST expression node

    Returns:
        True if node is settings.DEBUG
    """
    if not isinstance(node, ast.Attribute):
        return False

    if node.attr != "DEBUG":
        return False

    if isinstance(node.value, ast.Name) and node.value.id == "settings":
        return True

    return False


def main(file_paths: List[str]) -> int:
    """Run all safety checks on the given files.

    Args:
        file_paths: List of file paths to check

    Returns:
        Exit code: 0 if all checks pass, 1 if violations found
    """
    all_violations: List[Violation] = []

    for filepath in file_paths:
        path = Path(filepath)
        if not path.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            continue

        code = path.read_text(encoding="utf-8")

        violations = check_no_skip_decorators(code, filepath)
        all_violations.extend(violations)

        violations = check_debug_guard_in_dev_scripts(code, filepath)
        all_violations.extend(violations)

    for violation in all_violations:
        print(violation)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
