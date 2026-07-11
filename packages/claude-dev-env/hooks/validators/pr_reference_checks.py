"""PR and commit reference detection validator.

Implements check 6: No PR/commit references in comments.
Code comments must be timeless - no historical context.
"""

import re
import sys
from pathlib import Path
from typing import List

from .validator_base import Violation


PR_PATTERN = re.compile(r"#.*\bPR\s*#?\d+", re.IGNORECASE)
COMMIT_PATTERN = re.compile(r"#.*\bcommit\b", re.IGNORECASE)
ISSUE_PATTERN = re.compile(r"#.*(?:addresses|fixes|closes|resolves)\s*#\d+", re.IGNORECASE)
HASH_REF_PATTERN = re.compile(r"#\s*#\d+")


def check_pr_references(source: str, filename: str) -> List[Violation]:
    violations: List[Violation] = []
    lines = source.splitlines()

    for line_num, line in enumerate(lines, start=1):
        if PR_PATTERN.search(line):
            violations.append(
                Violation(filename, line_num, "PR reference in comment - comments should be timeless")
            )
        elif COMMIT_PATTERN.search(line):
            violations.append(
                Violation(filename, line_num, "Commit reference in comment - comments should be timeless")
            )
        elif ISSUE_PATTERN.search(line) or HASH_REF_PATTERN.search(line):
            violations.append(
                Violation(filename, line_num, "Issue reference in comment - comments should be timeless")
            )

    return violations


def validate_file(file_path: Path) -> List[Violation]:
    filename = str(file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as error:
        return [Violation(filename, 0, f"Error reading file: {error}")]

    return check_pr_references(source, filename)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: pr_reference_checks.py <file1> [file2 ...]", file=sys.stderr)
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
