"""Constants for the per-directory CLAUDE.md orphan-file-reference blocker.

A per-directory ``CLAUDE.md`` documents the files in its own directory subtree in
a markdown table whose first column names each file in backticks. When a
first-column cell names a bare filename that exists nowhere in that subtree, the
table points a reader at a file that is not there. This module holds the patterns
that find those cells, the filename extensions that mark a cell as a file
reference, the relative-path marker that exempts a cross-directory reference, the
subtree scan budget, and the block-message text the hook emits.
"""

import re

__all__ = [
    "CLAUDE_MD_FILENAME",
    "TABLE_ROW_PATTERN",
    "FIRST_COLUMN_BACKTICK_PATTERN",
    "SEPARATOR_CELL_PATTERN",
    "RELATIVE_PATH_SOURCE_PATTERN",
    "ALL_REFERENCED_FILE_EXTENSIONS",
    "MAX_SUBTREE_FILES_SCANNED",
    "MAX_ORPHAN_FILE_ISSUES",
    "ORPHAN_FILE_MESSAGE_TEMPLATE",
    "ORPHAN_FILE_SYSTEM_MESSAGE",
    "ORPHAN_FILE_ADDITIONAL_CONTEXT",
]

CLAUDE_MD_FILENAME: str = "CLAUDE.md"

TABLE_ROW_PATTERN: re.Pattern[str] = re.compile(r"^\s*\|")

FIRST_COLUMN_BACKTICK_PATTERN: re.Pattern[str] = re.compile(r"`([^`]+)`")

SEPARATOR_CELL_PATTERN: re.Pattern[str] = re.compile(r"^[\s:\-]+$")

RELATIVE_PATH_SOURCE_PATTERN: re.Pattern[str] = re.compile(r"\.\.[\\/]")

ALL_REFERENCED_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".md",
        ".json",
        ".mjs",
        ".js",
        ".ts",
        ".ps1",
        ".cmd",
        ".ahk",
        ".yml",
        ".yaml",
        ".sh",
        ".txt",
        ".cfg",
        ".toml",
        ".ini",
    }
)

MAX_SUBTREE_FILES_SCANNED: int = 5000

MAX_ORPHAN_FILE_ISSUES: int = 20

ORPHAN_FILE_MESSAGE_TEMPLATE: str = (
    "CLAUDE.md table references files that exist nowhere under {directory}: "
    "{missing}. A per-directory CLAUDE.md table names files in its own directory "
    "subtree; a first-column cell naming a file absent from that subtree points a "
    "reader at something that is not there. Drop the row, or correct the cell to "
    "name a file that exists in this directory or a subdirectory of it."
)

ORPHAN_FILE_SYSTEM_MESSAGE: str = (
    "CLAUDE.md table names a file that does not exist in its directory subtree - "
    "drop the row or name an existing file"
)

ORPHAN_FILE_ADDITIONAL_CONTEXT: str = (
    "Each first-column table cell wrapped in backticks that ends in a known file "
    "extension must name a file present in this CLAUDE.md's own directory or a "
    "subdirectory of it. Cells holding a path with a slash, a subdirectory ending "
    "in '/', or a slash-command are out of scope. A table whose content names an "
    "explicit relative-path source (a '../' token) documents files outside the "
    "subtree and is out of scope. For each missing file:\n"
    "  - delete the table row, or\n"
    "  - rename the cell to an existing file in this directory subtree."
)
