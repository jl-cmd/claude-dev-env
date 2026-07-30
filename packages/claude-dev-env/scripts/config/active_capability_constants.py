"""Constants for active skill/agent/command reference resolution."""

from __future__ import annotations

PACKAGE_SKILLS_DIRECTORY: str = "skills"
PACKAGE_AGENTS_DIRECTORY: str = "agents"
PACKAGE_COMMANDS_DIRECTORY: str = "commands"
SKILL_MANIFEST_FILENAME: str = "SKILL.md"

CAPABILITY_KIND_SKILL: str = "skill"
CAPABILITY_KIND_AGENT: str = "agent"
CAPABILITY_KIND_COMMAND: str = "command"

# Slash-command and skill names that must never appear as active instructions.
ALL_BANNED_ACTIVE_CAPABILITY_NAMES: frozenset[str] = frozenset(
    {
        "stub-detector",
        "superpowers",
        "qbug",
        "findbugs",
        "fixbugs",
        "monitor-open-prs",
    }
)

# Fence languages treated as inert historical/example content.
ALL_INERT_FENCE_LANGUAGES: frozenset[str] = frozenset(
    {
        "example",
        "history",
        "historical",
        "quote",
        "diff",
    }
)

SLASH_CAPABILITY_PATTERN: str = r"(?<![`\w])/([a-z][a-z0-9-]{2,})"
BACKTICK_CAPABILITY_PATTERN: str = (
    r"`(?:skills/)?([a-z][a-z0-9-]{2,})(?:/SKILL\.md)?`"
)

UTF8_ENCODING: str = "utf-8"
NEWLINE_JOIN_SEPARATOR: str = "\n"
