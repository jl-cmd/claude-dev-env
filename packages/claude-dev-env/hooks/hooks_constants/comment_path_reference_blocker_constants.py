"""Constants for the comment path-reference blocker.

Holds the tool-name set, the CI-workflow file recognizers, the comment-line and
path-token patterns, the base-directory recognizer, the bounded-scan budgets, the
noise-directory prune set, and the block-message strings. The blocker imports each
of these by name.
"""

from __future__ import annotations

import re

__all__ = [
    "ALL_WRITE_EDIT_TOOL_NAMES",
    "GITHUB_WORKFLOWS_PATH_MARKER",
    "ALL_WORKFLOW_FILE_EXTENSIONS",
    "COMMENT_LINE_PATTERN",
    "WORKING_DIRECTORY_PATTERN",
    "PATH_TOKEN_PATTERN",
    "ALL_REFERENCE_FILE_EXTENSIONS",
    "ALL_TOKEN_PLACEHOLDER_CHARACTERS",
    "URL_SCHEME_MARKER",
    "GIT_DIRECTORY_NAME",
    "ALL_NOISE_DIRECTORY_NAMES",
    "NEWLINE_JOIN_SEPARATOR",
    "COMMA_SPACE_JOIN_SEPARATOR",
    "MAX_SUBTREE_FILES_SCANNED",
    "MAX_UNRESOLVED_ISSUES",
    "UNRESOLVED_MESSAGE_TEMPLATE",
    "UNRESOLVED_ADDITIONAL_CONTEXT",
    "UNRESOLVED_SYSTEM_MESSAGE",
]

ALL_WRITE_EDIT_TOOL_NAMES: frozenset[str] = frozenset({"Write", "Edit", "MultiEdit"})

GITHUB_WORKFLOWS_PATH_MARKER = ".github/workflows/"
ALL_WORKFLOW_FILE_EXTENSIONS: frozenset[str] = frozenset({".yml", ".yaml"})

COMMENT_LINE_PATTERN = re.compile(r"^\s*#\s?(.*)$")
WORKING_DIRECTORY_PATTERN = re.compile(r"^\s*working-directory:\s*[\"']?([^\"'\s]+)")
PATH_TOKEN_PATTERN = re.compile(
    r"(?<![\w./-])([A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+\.[A-Za-z0-9]{1,5})"
)

ALL_REFERENCE_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".mjs",
        ".js",
        ".ts",
        ".ps1",
        ".sh",
        ".yml",
        ".yaml",
        ".json",
        ".toml",
        ".cfg",
        ".ini",
        ".txt",
    }
)
ALL_TOKEN_PLACEHOLDER_CHARACTERS: frozenset[str] = frozenset(
    {"*", "?", "{", "}", "<", ">", "$", "%", "~"}
)
URL_SCHEME_MARKER = "://"

GIT_DIRECTORY_NAME = ".git"
ALL_NOISE_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)

NEWLINE_JOIN_SEPARATOR = "\n"
COMMA_SPACE_JOIN_SEPARATOR = ", "

MAX_SUBTREE_FILES_SCANNED = 40000
MAX_UNRESOLVED_ISSUES = 20

UNRESOLVED_MESSAGE_TEMPLATE = (
    "Comment in {file} cites a repository path that does not resolve: {paths}. Each "
    "cited path resolves against neither the repository root nor any job "
    "working-directory, yet a file of that name lives elsewhere in the tree, so the "
    "comment points a reader at a path the repository does not hold. Correct the "
    "comment to name the path the file actually lives at."
)
UNRESOLVED_ADDITIONAL_CONTEXT = (
    "A CI-workflow comment that names a collection path (for example "
    "`config/tests/test_x.py`) must name a path that resolves under the repository "
    "root or the job's `working-directory`. When the named path resolves nowhere yet "
    "its filename exists at a different path, the comment misattributes the file. "
    "Name the resolving path, or drop the path from the comment."
)
UNRESOLVED_SYSTEM_MESSAGE = (
    "Blocked: a workflow comment cites a repository path that does not resolve."
)
