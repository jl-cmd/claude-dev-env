"""Security vulnerability detection validator.

Implements:
- Check 27: Hardcoded secrets (API keys, passwords, tokens)
- Check 28: SQL injection risk (f-strings/format in SQL)
- Check 29: XSS risk (mark_safe without sanitization)
"""

import ast
import re
import sys
from pathlib import Path
from typing import List

from .validator_base import Violation


SECRET_PATTERNS: frozenset[str] = frozenset({
    "api_key", "apikey", "api-key",
    "password", "passwd", "pwd",
    "secret", "token", "auth",
    "private_key", "privatekey",
    "credential", "credentials",
})

SQL_EXECUTE_PATTERN = re.compile(r"\.execute\s*\(\s*f['\"]|\.execute\s*\([^)]*\.format\(", re.IGNORECASE)


def check_hardcoded_secrets(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id.lower()
                    if any(pattern in var_name for pattern in SECRET_PATTERNS):
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            if len(node.value.value) > 3:
                                violations.append(
                                    Violation(
                                        filename,
                                        node.lineno,
                                        f"Hardcoded secret in '{target.id}' - use environment variable",
                                    )
                                )

    return violations


def check_sql_injection(source: str, filename: str) -> List[Violation]:
    violations: List[Violation] = []
    lines = source.splitlines()

    for line_num, line in enumerate(lines, start=1):
        if SQL_EXECUTE_PATTERN.search(line):
            violations.append(
                Violation(
                    filename,
                    line_num,
                    "SQL injection risk - use parameterized queries instead of f-string/format",
                )
            )

    return violations


def check_xss_risk(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "mark_safe":
                violations.append(
                    Violation(
                        filename,
                        node.lineno,
                        "XSS risk - mark_safe() on user input is dangerous",
                    )
                )
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "mark_safe":
                violations.append(
                    Violation(
                        filename,
                        node.lineno,
                        "XSS risk - mark_safe() on user input is dangerous",
                    )
                )

    return violations


def validate_file(file_path: Path) -> List[Violation]:
    violations: List[Violation] = []
    filename = str(file_path)

    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as error:
        return [Violation(filename, 0, f"Error reading file: {error}")]

    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [Violation(filename, error.lineno or 0, f"Syntax error: {error.msg}")]

    violations.extend(check_hardcoded_secrets(tree, filename))
    violations.extend(check_sql_injection(source, filename))
    violations.extend(check_xss_risk(tree, filename))

    return violations


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: security_checks.py <file1.py> [file2.py ...]", file=sys.stderr)
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
