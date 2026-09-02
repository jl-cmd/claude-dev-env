"""Base classes for validators.

Provides shared dataclasses used across all validator modules, and the one
read and the one parse each of those modules shares for a given file.
"""

import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config.validator_base_constants import SOURCE_CACHE_ENTRIES, SOURCE_ENCODING


@dataclass(frozen=True)
class Violation:
    """Represents a validation violation."""

    file: str
    line: int
    message: str

    def __str__(self) -> str:
        """Format as file:line: message."""
        return f"{self.file}:{self.line}: {self.message}"


@dataclass(frozen=True)
class ValidatorResult:
    """Result from running a validator."""

    name: str
    checks: str
    passed: bool
    output: str
    skipped: bool = False


@lru_cache(maxsize=SOURCE_CACHE_ENTRIES)
def _source_text_for_stat(
    file_path_text: str, modified_nanoseconds: int, size_in_bytes: int
) -> str:
    """Read one file, keyed on the stat that identifies this version of it."""
    return Path(file_path_text).read_text(encoding=SOURCE_ENCODING)


def source_text(file_path: Path) -> str:
    """Return the file's text, reading it once however many checks ask.

    Every check the save-path gate runs reads the same file. The gate hands
    each of them one freshly written target, so the read is repeated work.
    The cache key carries the modification time and size, so an edited file
    is read again.

    Raises whatever ``read_text`` raises, so a caller's own error handling
    is unchanged.

    Args:
        file_path: The file to read.

    Returns:
        The file's decoded text.
    """
    file_status = file_path.stat()
    return _source_text_for_stat(
        str(file_path), file_status.st_mtime_ns, file_status.st_size
    )


@lru_cache(maxsize=SOURCE_CACHE_ENTRIES)
def syntax_tree(source: str) -> ast.Module:
    """Return the parsed tree for source, parsing it once however many checks ask.

    No check mutates the tree; each one walks it. So one parse serves all of
    them, and the tree is shared rather than copied.

    Raises ``SyntaxError`` exactly as ``ast.parse`` does, so a caller's own
    error handling is unchanged.

    Args:
        source: The file's text.

    Returns:
        The parsed module.
    """
    return ast.parse(source)
