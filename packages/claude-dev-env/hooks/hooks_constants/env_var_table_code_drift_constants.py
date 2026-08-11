"""Constants for the env-var-table code-drift blocker.

Holds the markdown filename matcher, the table-row and cell patterns, the
env-var-name and code-file-extension recognizers, the bounded-scan budgets, and
the block-message strings. The blocker imports each of these by name.
"""

from __future__ import annotations

import re

__all__ = [
    "MARKDOWN_FILE_EXTENSION",
    "TABLE_ROW_PATTERN",
    "CODE_FENCE_PATTERN",
    "SEPARATOR_CELL_PATTERN",
    "BACKTICK_TOKEN_PATTERN",
    "ENV_VAR_NAME_PATTERN",
    "ALL_CODE_FILE_EXTENSIONS",
    "ALL_NOISE_DIRECTORY_NAMES",
    "GIT_DIRECTORY_NAME",
    "MINIMUM_ENV_VAR_ROW_CELL_COUNT",
    "MAX_SUBTREE_FILES_SCANNED",
    "MAX_DRIFT_ISSUES",
    "DRIFT_MESSAGE_TEMPLATE",
    "DRIFT_ADDITIONAL_CONTEXT",
    "DRIFT_SYSTEM_MESSAGE",
]

MARKDOWN_FILE_EXTENSION = ".md"

TABLE_ROW_PATTERN = re.compile(r"^\s*\|")
CODE_FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
SEPARATOR_CELL_PATTERN = re.compile(r"^[:\-\s]+$")
BACKTICK_TOKEN_PATTERN = re.compile(r"`([^`]+)`")
ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,}$")

ALL_CODE_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".mjs", ".js", ".ts", ".ps1", ".sh"}
)
ALL_NOISE_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {".git", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)

GIT_DIRECTORY_NAME = ".git"
MINIMUM_ENV_VAR_ROW_CELL_COUNT = 2

MAX_SUBTREE_FILES_SCANNED = 20000
MAX_DRIFT_ISSUES = 20

DRIFT_MESSAGE_TEMPLATE = (
    "Update the env-var summary table in {file} for this variable and code-file "
    "pair: {drift}. Point the row to the variable the code reads."
)
DRIFT_ADDITIONAL_CONTEXT = (
    "Each `VARIABLE` | `code/file.py` row in a markdown env-var summary table "
    "names a code file that reads that variable. Update every row to match the "
    "variable/file pair the code reads. Point each row to the variable and file "
    "pair the code reads."
)
DRIFT_SYSTEM_MESSAGE = "Update the env-var summary table to match the variable each code file reads."
