"""Configuration constants for the md_to_html_blocker PreToolUse hook."""

from __future__ import annotations


ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES: frozenset[str] = frozenset(
    {"agents", "docs", "skills", "rules", "system-prompts", "commands"}
)

PACKAGES_TOP_LEVEL_SEGMENT: str = "packages"
CLAUDE_DEV_ENV_REPO_NAME_SEGMENT: str = "claude-dev-env"

WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH: int = 2

MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR: int = 4


__all__ = [
    "ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES",
    "CLAUDE_DEV_ENV_REPO_NAME_SEGMENT",
    "MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR",
    "PACKAGES_TOP_LEVEL_SEGMENT",
    "WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH",
]
