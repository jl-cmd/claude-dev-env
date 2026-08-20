"""Shared CLI utilities for pr-loop scripts."""

from __future__ import annotations

import sys
from pathlib import Path


def require_file(file_path: Path, label: str) -> int | None:
    """Verify a required file exists, returning an exit code when absent.

    Args:
        file_path: Path to the required file.
        label: Human-readable label for the error message.

    Returns:
        None when the file exists (caller continues), or 1 when absent.
    """
    if not file_path.is_file():
        print(f"{label} not found: {file_path}", file=sys.stderr)
        return 1
    return None
