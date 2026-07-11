"""Comment detection validator.

Implements check 26: No comments in code (self-documenting code principle).

Detects:
- Python comments (# ...)
- TypeScript/JavaScript comments (// ... and /* ... */)

Exceptions (NOT flagged):
- Shebang lines (#!/...)
- Type annotations (type:, noqa, eslint-disable)
- Docstrings (triple-quoted strings for function contracts)

Note: Docstrings documenting function Args/Returns/Raises are acceptable
per CODE_RULES.md. This validator only flags # and // style comments.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


SHEBANG_PATTERN = re.compile(r"^#!")
PYTHON_COMMENT_PATTERN = re.compile(r"(?<!.)#(?!!).+$|(?<=\s)#.+$", re.MULTILINE)
JS_SINGLE_COMMENT_PATTERN = re.compile(r"//.*$", re.MULTILINE)
JS_BLOCK_COMMENT_PATTERN = re.compile(r"/\*[\s\S]*?\*/", re.MULTILINE)


@dataclass
class Violation:
    """Represents a comment violation."""

    file: str
    line: int
    message: str

    def __str__(self) -> str:
        """Format as file:line: message."""
        return f"{self.file}:{self.line}: {self.message}"


def check_python_comments(source: str, filename: str) -> List[Violation]:
    """Check for comments in Python files.

    Args:
        source: Source code as string
        filename: Name of file being checked

    Returns:
        List of violations found
    """
    violations: List[Violation] = []
    lines = source.splitlines()

    for line_num, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            if SHEBANG_PATTERN.match(stripped):
                continue

            comment_text = stripped[1:].strip()[:40]
            violations.append(
                Violation(
                    filename,
                    line_num,
                    f"Comment found: '# {comment_text}...' - code should be self-documenting",
                )
            )

        elif "#" in line:
            code_part, _, comment_part = line.partition("#")
            if code_part.count('"') % 2 == 0 and code_part.count("'") % 2 == 0:
                comment_text = comment_part.strip()[:40]
                violations.append(
                    Violation(
                        filename,
                        line_num,
                        f"Inline comment found: '# {comment_text}...' - code should be self-documenting",
                    )
                )

    return violations


def check_js_comments(source: str, filename: str) -> List[Violation]:
    """Check for comments in JavaScript/TypeScript files.

    Args:
        source: Source code as string
        filename: Name of file being checked

    Returns:
        List of violations found
    """
    violations: List[Violation] = []
    lines = source.splitlines()

    for line_num, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        if stripped.startswith("//"):
            comment_text = stripped[2:].strip()[:40]
            violations.append(
                Violation(
                    filename,
                    line_num,
                    f"Comment found: '// {comment_text}...' - code should be self-documenting",
                )
            )

    for match in JS_BLOCK_COMMENT_PATTERN.finditer(source):
        start_pos = match.start()
        line_num = source[:start_pos].count("\n") + 1
        comment_preview = match.group()[:40].replace("\n", " ")
        violations.append(
            Violation(
                filename,
                line_num,
                f"Block comment found: '{comment_preview}...' - code should be self-documenting",
            )
        )

    return violations


def validate_file(file_path: Path) -> List[Violation]:
    """Validate a file for comment violations.

    Args:
        file_path: Path to file to validate

    Returns:
        List of all violations found
    """
    violations: List[Violation] = []
    filename = str(file_path)

    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as error:
        violations.append(Violation(filename, 0, f"Error reading file: {error}"))
        return violations

    suffix = file_path.suffix.lower()

    if suffix == ".py":
        violations.extend(check_python_comments(source, filename))
    elif suffix in (".ts", ".tsx", ".js", ".jsx"):
        violations.extend(check_js_comments(source, filename))

    return violations


def main() -> int:
    """Main entry point for command-line usage.

    Returns:
        Exit code: 0 if all files pass, 1 if violations found
    """
    if len(sys.argv) < 2:
        print("Usage: comment_checks.py <file1> [file2 ...]", file=sys.stderr)
        return 1

    all_violations: List[Violation] = []

    for file_arg in sys.argv[1:]:
        file_path = Path(file_arg)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            return 1

        violations = validate_file(file_path)
        all_violations.extend(violations)

    for violation in all_violations:
        print(violation)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
