"""File structure validation checks for pre-PR validation."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


EXCLUDED_DIRS = {".venv", "venv", "node_modules", ".git"}

# Django requires empty __init__.py in these directories for module discovery
DJANGO_REQUIRED_INIT_DIRS = {
    "migrations",
    "management",
    "commands",
    "templatetags",
}

# Files that indicate a directory is a Django app
DJANGO_APP_INDICATORS = {
    "apps.py",
    "models.py",
    "views.py",
    "admin.py",
    "settings.py",
    "urls.py",
}


@dataclass(frozen=True)
class Violation:
    """Represents a validation violation."""

    file: str
    line: int
    message: str


def _normalize_path(path: Path, project_root: Path) -> str:
    """
    Convert Path to normalized string with forward slashes.

    Args:
        path: Path to normalize
        project_root: Project root for relative path calculation

    Returns:
        Normalized path string with forward slashes
    """
    relative = path.relative_to(project_root)
    return relative.as_posix()


def _should_exclude_path(path: Path, project_root: Path) -> bool:
    """Check if path should be excluded from validation."""
    try:
        relative = path.relative_to(project_root)
        return any(part in EXCLUDED_DIRS for part in relative.parts)
    except ValueError:
        return False


def check_multiple_requirements_txt(project_root: Path) -> List[Violation]:
    """
    Check for multiple requirements.txt files in project.

    Args:
        project_root: Root directory of the project

    Returns:
        List of violations found (empty if single or no requirements.txt)
    """
    requirements_files: List[Path] = []

    for req_file in project_root.rglob("requirements.txt"):
        if not _should_exclude_path(req_file, project_root):
            requirements_files.append(req_file)

    if len(requirements_files) <= 1:
        return []

    extra_files = [
        _normalize_path(f, project_root)
        for f in requirements_files
        if f != project_root / "requirements.txt"
    ]

    message = (
        f"Multiple requirements.txt files found. "
        f"Project should have exactly one requirements.txt at root. "
        f"Extra files: {', '.join(extra_files)}"
    )

    return [Violation(file="requirements.txt", line=1, message=message)]


def _is_django_required_init(init_file: Path) -> bool:
    """Check if __init__.py is in a Django-required directory or Django app."""
    parent = init_file.parent
    parent_name = parent.name

    # Check if in known Django-required directory
    if parent_name in DJANGO_REQUIRED_INIT_DIRS:
        return True

    # Check if this is a Django app directory (contains apps.py, models.py, etc.)
    for indicator in DJANGO_APP_INDICATORS:
        if (parent / indicator).exists():
            return True

    return False


def check_empty_init_files(project_root: Path) -> List[Violation]:
    """
    Check for empty __init__.py files that serve no purpose.

    Excludes Django-required directories (migrations, management, commands, templatetags)
    which need empty __init__.py for module discovery.

    Args:
        project_root: Root directory of the project

    Returns:
        List of violations found (one per empty __init__.py)
    """
    violations: List[Violation] = []

    for init_file in project_root.rglob("__init__.py"):
        if _should_exclude_path(init_file, project_root):
            continue

        # Skip Django-required empty inits
        if _is_django_required_init(init_file):
            continue

        content = init_file.read_text(encoding="utf-8")
        if not content.strip():
            relative_path = _normalize_path(init_file, project_root)
            message = (
                "Empty __init__.py file serves no purpose. "
                "Either add exports/initialization or delete the file."
            )
            violations.append(Violation(file=relative_path, line=1, message=message))

    return violations


def main(args: List[str]) -> None:
    """
    Run all file structure checks and print violations.

    Args:
        args: Command line arguments (expects project root path)

    Exits:
        0 if all checks pass, 1 if violations found or invalid usage
    """
    if len(args) == 0:
        print("Usage: python file_structure_checks.py <project_root>")
        sys.exit(1)

    project_root = Path(args[0])
    if not project_root.exists():
        print(f"Error: Project root does not exist: {project_root}")
        sys.exit(1)

    all_violations: List[Violation] = []

    all_violations.extend(check_multiple_requirements_txt(project_root))
    all_violations.extend(check_empty_init_files(project_root))

    if all_violations:
        for violation in all_violations:
            print(f"{violation.file}:{violation.line}: {violation.message}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])
