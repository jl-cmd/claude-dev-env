"""Read on-disk file text, enumerate changed files, and apply style fixes."""

import subprocess
from pathlib import Path
from typing import List, Optional

from .config import (
    ALL_GIT_LAST_COMMIT_DIFF_COMMAND,
    ALL_GIT_STAGED_DIFF_COMMAND,
    PYTHON_EXTENSION,
)
from .python_style_checks import fix_file


def _read_target_file_content(file_path: str) -> Optional[str]:
    """Return the on-disk content of *file_path*, or None when it cannot be read."""
    try:
        with open(file_path, "r", encoding="utf-8") as readable_file:
            return readable_file.read()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None


def get_changed_files() -> List[Path]:
    """Get list of files changed in current commit/staging."""
    result = subprocess.run(
        ALL_GIT_STAGED_DIFF_COMMAND,
        capture_output=True,
        text=True,
        check=False,
    )

    files = result.stdout.strip().split("\n") if result.stdout.strip() else []

    if not files:
        result = subprocess.run(
            ALL_GIT_LAST_COMMIT_DIFF_COMMAND,
            capture_output=True,
            text=True,
            check=False,
        )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []

    return [Path(each_file) for each_file in files if each_file]


def fix_python_style(files: List[Path]) -> List[str]:
    """Apply Python style fixes to files.

    Args:
        files: List of files to fix

    Returns:
        List of files that were fixed
    """
    fixed_files: List[str] = []
    py_files = [each_file for each_file in files if each_file.suffix == PYTHON_EXTENSION]

    for each_file in py_files:
        if fix_file(each_file):
            fixed_files.append(str(each_file))

    return fixed_files
