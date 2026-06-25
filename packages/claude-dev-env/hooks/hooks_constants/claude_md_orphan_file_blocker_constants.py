"""Constants for the per-directory CLAUDE.md orphan-file-reference blocker.

A per-directory ``CLAUDE.md`` documents the files reachable from its own
directory in a markdown table whose first column names each file in backticks,
and shows run commands inside fenced code blocks that invoke those files. When a
first-column cell, or an interpreter invocation inside a run-command fence
(``python script.py``), names a bare filename that exists nowhere under the scan
root (the CLAUDE.md directory's parent, covering the directory, its
subdirectories, and its siblings), the doc points a reader at a file that is not
there. This module holds the patterns that find those cells and run-command
invocations, the filename extensions that mark a cell or invocation as a file
reference, the region-boundary marker that scopes a prose region to one section,
the relative-path marker that exempts a cross-directory table block, the
directory names the subtree walk prunes, the subtree scan budget, and the
block-message text the hook emits.
"""

import re

__all__ = [
    "CLAUDE_MD_FILENAME",
    "TABLE_ROW_PATTERN",
    "CODE_FENCE_PATTERN",
    "FIRST_COLUMN_BACKTICK_PATTERN",
    "SEPARATOR_CELL_PATTERN",
    "REGION_BOUNDARY_PATTERN",
    "RELATIVE_PATH_SOURCE_PATTERN",
    "RUN_COMMAND_SCRIPT_PATTERN",
    "ALL_REFERENCED_FILE_EXTENSIONS",
    "ALL_RUN_COMMAND_SCRIPT_EXTENSIONS",
    "ALL_NOISE_DIRECTORY_NAMES",
    "MAX_SUBTREE_FILES_SCANNED",
    "MAX_ORPHAN_FILE_ISSUES",
    "ORPHAN_FILE_MESSAGE_TEMPLATE",
    "ORPHAN_FILE_SYSTEM_MESSAGE",
    "ORPHAN_FILE_ADDITIONAL_CONTEXT",
]

CLAUDE_MD_FILENAME: str = "CLAUDE.md"

TABLE_ROW_PATTERN: re.Pattern[str] = re.compile(r"^\s*\|")

CODE_FENCE_PATTERN: re.Pattern[str] = re.compile(r"^\s*(?:```|~~~)")

FIRST_COLUMN_BACKTICK_PATTERN: re.Pattern[str] = re.compile(r"`([^`]+)`")

SEPARATOR_CELL_PATTERN: re.Pattern[str] = re.compile(r"^[\s:\-]+$")

REGION_BOUNDARY_PATTERN: re.Pattern[str] = re.compile(r"^\s*#")

RELATIVE_PATH_SOURCE_PATTERN: re.Pattern[str] = re.compile(r"\.\.[\\/]")

RUN_COMMAND_SCRIPT_PATTERN: re.Pattern[str] = re.compile(
    r"(?<![\w.])(?:python(?:\.exe)?|python3|node|pwsh|powershell(?:\.exe)?|bash|sh|ruby|perl)"
    r"\b(?:\s+-\S+(?:\s+[\w./\\-]+(?=\s+\S))?)*"
    r"\s+[\"']?"
    r"([\w./\\-]+\.(?:py|mjs|js|ts|ps1|sh|rb|pl))\b"
)

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

ALL_RUN_COMMAND_SCRIPT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".mjs",
        ".js",
        ".ts",
        ".ps1",
        ".sh",
        ".rb",
        ".pl",
    }
)

ALL_NOISE_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
    }
)

MAX_SUBTREE_FILES_SCANNED: int = 5000

MAX_ORPHAN_FILE_ISSUES: int = 20

ORPHAN_FILE_MESSAGE_TEMPLATE: str = (
    "CLAUDE.md references files that exist nowhere under {directory}: "
    "{missing}. A per-directory CLAUDE.md names files in its own directory "
    "subtree, both in its table cells and in the run commands its fenced code "
    "blocks show; a cell or a run command naming a file absent from that subtree "
    "points a reader at something that is not there. Drop the row or run command, "
    "or correct it to name a file that exists in this directory, a subdirectory of "
    "it, or a sibling directory under its parent."
)

ORPHAN_FILE_SYSTEM_MESSAGE: str = (
    "CLAUDE.md names a file that does not exist in its directory subtree - "
    "drop the row or run command, or name an existing file"
)

ORPHAN_FILE_ADDITIONAL_CONTEXT: str = (
    "Each first-column table cell wrapped in backticks that ends in a known file "
    "extension, and each script an interpreter invocation inside a fenced run "
    "command names (such as 'python script.py'), must name a file present under "
    "the scan root: this CLAUDE.md's own directory, a subdirectory of it, or a "
    "sibling directory under its parent. Cells holding a path with a slash, a "
    "subdirectory ending in '/', or a slash-command are out of scope. A table "
    "whose own block names an explicit relative-path source (a '../' token) "
    "documents files outside the subtree and is out of scope. For each missing "
    "file:\n"
    "  - delete the table row or the run command, or\n"
    "  - rename it to an existing file under the scan root."
)
