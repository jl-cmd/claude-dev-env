"""Configuration constants for the open_questions_in_plans_blocker PreToolUse hook."""

from __future__ import annotations

from re import IGNORECASE, MULTILINE, Pattern, compile


MARKDOWN_EXTENSION: str = ".md"

PLANS_PATH_SEGMENT: str = "/.claude/plans/"
PLANS_PATH_PREFIX: str = ".claude/plans/"
DOCS_PLANS_PATH_SEGMENT: str = "/docs/plans/"
DOCS_PLANS_PATH_PREFIX: str = "docs/plans/"

PLAN_FILE_ENCODING: str = "utf-8"

UNREADABLE_FILE_SYNTHETIC_CONTENT: str = "## Open Questions\n"

OPEN_QUESTIONS_HEADING_PATTERN: Pattern[str] = compile(
    r"^\s*(?:#{1,6}\s+|\*\*\s*|__\s*)open[\s_-]+questions(?:[^A-Za-z0-9]|$)",
    IGNORECASE | MULTILINE,
)

CODE_FENCE_PATTERN: Pattern[str] = compile(r"```[\s\S]*?```")
INLINE_CODE_PATTERN: Pattern[str] = compile(r"``[^`\n]+``|`[^`\n]+`")


__all__ = [
    "CODE_FENCE_PATTERN",
    "DOCS_PLANS_PATH_PREFIX",
    "DOCS_PLANS_PATH_SEGMENT",
    "INLINE_CODE_PATTERN",
    "MARKDOWN_EXTENSION",
    "OPEN_QUESTIONS_HEADING_PATTERN",
    "PLANS_PATH_PREFIX",
    "PLANS_PATH_SEGMENT",
    "PLAN_FILE_ENCODING",
    "UNREADABLE_FILE_SYNTHETIC_CONTENT",
]
