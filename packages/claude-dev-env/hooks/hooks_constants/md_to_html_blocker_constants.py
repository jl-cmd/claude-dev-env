"""Configuration constants for the md_to_html_blocker PreToolUse hook
and its shared exemption helpers (`md_path_exemptions`)."""

from __future__ import annotations

import os
import tempfile


ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES: frozenset[str] = frozenset(
    {"agents", "docs", "skills", "rules", "system-prompts", "commands"}
)

PACKAGES_TOP_LEVEL_SEGMENT: str = "packages"
CLAUDE_DEV_ENV_REPO_NAME_SEGMENT: str = "claude-dev-env"

MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR: int = 4

ALL_EXEMPT_ANYWHERE_FILENAMES: tuple[str, ...] = ("SKILL.md",)
ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS: tuple[str, ...] = ("agents", "skills", "commands")
ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES: tuple[str, ...] = ("SessionLog",)
ALL_EXEMPT_ROOT_FILENAMES: tuple[str, ...] = ("readme.md", "changelog.md")
REPO_ROOT_MARKER_NAME: str = ".git"
CLAUDE_DIRECTORY_NAME: str = ".claude"
PLUGIN_ROOT_MARKER_DIRECTORY_NAME: str = ".claude-plugin"

CLAUDE_DIRECTORY_SEGMENT_MARKER: str = f"/{CLAUDE_DIRECTORY_NAME}/"
CLAUDE_DIRECTORY_PATH_PREFIX: str = f"{CLAUDE_DIRECTORY_NAME}/"
PLUGIN_DIRECTORY_SEGMENT_MARKER: str = f"/{PLUGIN_ROOT_MARKER_DIRECTORY_NAME}/"
PLUGIN_DIRECTORY_PATH_PREFIX: str = f"{PLUGIN_ROOT_MARKER_DIRECTORY_NAME}/"

ALL_EXEMPT_ANYWHERE_FILENAMES_LOWER: frozenset[str] = frozenset(
    each_filename.lower() for each_filename in ALL_EXEMPT_ANYWHERE_FILENAMES
)
ALL_EXEMPT_ROOT_FILENAMES_LOWER: frozenset[str] = frozenset(
    each_filename.lower() for each_filename in ALL_EXEMPT_ROOT_FILENAMES
)


def _resolve_canonical_directory_lowercase(directory_path: str) -> str:
    return (
        os.path.realpath(directory_path).replace("\\", "/").rstrip("/").lower()
    )


RESOLVED_HOME_DIRECTORY_LOWER: str = _resolve_canonical_directory_lowercase(
    os.path.expanduser("~")
)
RESOLVED_TEMP_DIRECTORY_LOWER: str = _resolve_canonical_directory_lowercase(
    tempfile.gettempdir()
)

ALL_EXEMPT_HOME_DIRECTORY_PATH_PREFIXES: tuple[str, ...] = tuple(
    f"{RESOLVED_HOME_DIRECTORY_LOWER}/{each_relative_directory.lower()}/"
    for each_relative_directory in ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES
)
RESOLVED_TEMP_DIRECTORY_PATH_PREFIX: str = f"{RESOLVED_TEMP_DIRECTORY_LOWER}/"


__all__ = [
    "ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES",
    "ALL_EXEMPT_ANYWHERE_FILENAMES",
    "ALL_EXEMPT_ANYWHERE_FILENAMES_LOWER",
    "ALL_EXEMPT_HOME_DIRECTORY_PATH_PREFIXES",
    "ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES",
    "ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS",
    "ALL_EXEMPT_ROOT_FILENAMES",
    "ALL_EXEMPT_ROOT_FILENAMES_LOWER",
    "CLAUDE_DEV_ENV_REPO_NAME_SEGMENT",
    "CLAUDE_DIRECTORY_NAME",
    "CLAUDE_DIRECTORY_PATH_PREFIX",
    "CLAUDE_DIRECTORY_SEGMENT_MARKER",
    "MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR",
    "PACKAGES_TOP_LEVEL_SEGMENT",
    "PLUGIN_DIRECTORY_PATH_PREFIX",
    "PLUGIN_DIRECTORY_SEGMENT_MARKER",
    "PLUGIN_ROOT_MARKER_DIRECTORY_NAME",
    "REPO_ROOT_MARKER_NAME",
    "RESOLVED_HOME_DIRECTORY_LOWER",
    "RESOLVED_TEMP_DIRECTORY_LOWER",
    "RESOLVED_TEMP_DIRECTORY_PATH_PREFIX",
]
