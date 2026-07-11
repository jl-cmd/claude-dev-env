"""TODO/FIXME tracking validator.

Implements check 36: TODO without issue reference.
"""

import re
import sys
from pathlib import Path
from typing import List

from .validator_base import Violation


TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME)\b(?!.*#\d+)", re.IGNORECASE)


def check_untracked_todos(source: str, filename: str) -> List[Violation]:
    violations: List[Violation] = []
    lines = source.splitlines()

    for line_num, line in enumerate(lines, start=1):
        if TODO_PATTERN.search(line):
            violations.append(
                Violation(
                    filename,
                    line_num,
                    "TODO/FIXME without issue reference - add #<issue_number>",
                )
            )

    return violations


def validate_file(file_path: Path) -> List[Violation]:
    filename = str(file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
    except Exception as error:
        return [Violation(filename, 0, f"Error reading file: {error}")]

    return check_untracked_todos(source, filename)


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
