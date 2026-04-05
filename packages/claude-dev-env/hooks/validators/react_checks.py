"""React code quality validators.

Validates React-specific code standards:
- No class components (use functional components with hooks)
- Exception: Error boundaries (until React adds hook-based error boundaries)
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Violation:
    """Represents a validation violation."""
    file: str
    line: int
    message: str


CLASS_COMPONENT_PATTERN = re.compile(
    r'^\s*class\s+\w+\s+extends\s+(Component|React\.Component|PureComponent|React\.PureComponent)\b',
    re.MULTILINE
)

CLASS_KEYWORD_PATTERN = re.compile(r'\bclass\b')

ERROR_BOUNDARY_PATTERN = re.compile(
    r'\b(componentDidCatch|getDerivedStateFromError)\b'
)


def check_no_class_components(file_paths: list[str]) -> list[Violation]:
    """Check that no class components exist (except error boundaries).

    Args:
        file_paths: List of file paths to check

    Returns:
        List of violations found
    """
    violations: list[Violation] = []

    for file_path_str in file_paths:
        file_path = Path(file_path_str)

        if file_path.suffix not in {'.tsx', '.jsx'}:
            continue

        content = file_path.read_text(encoding='utf-8')

        if ERROR_BOUNDARY_PATTERN.search(content):
            continue

        for match in CLASS_COMPONENT_PATTERN.finditer(content):
            class_match = CLASS_KEYWORD_PATTERN.search(match.group(0))
            if class_match:
                class_position = match.start() + class_match.start()
                line_num = content[:class_position].count('\n') + 1
                violations.append(Violation(
                    file=file_path_str,
                    line=line_num,
                    message="Use functional components with hooks instead of class components"
                ))

    return violations


def main() -> int:
    """Main entry point for command-line usage.

    Returns:
        Exit code: 0 if all checks pass, 1 if violations found
    """
    if len(sys.argv) < 2:
        print("Usage: python react_checks.py <file1> [file2] ...", file=sys.stderr)
        return 1

    file_paths = sys.argv[1:]
    violations = check_no_class_components(file_paths)

    for violation in violations:
        print(f"{violation.file}:{violation.line}: {violation.message}")

    return 1 if violations else 0


if __name__ == '__main__':
    sys.exit(main())
