"""Constants for the active_capability_references script.

Script-level scalar constants live in dev_env_scripts_constants alongside
timing.py and the other per-script constant modules.
"""

from __future__ import annotations

PACKAGE_AGENTS_HOME_DIRECTORY: str = ".agents"
PACKAGE_SKILLS_DIRECTORY: str = ".agents/skills"
PACKAGE_AGENTS_DIRECTORY: str = ".agents/agents"
PACKAGE_COMMANDS_DIRECTORY: str = "commands"
PACKAGE_ROOT_SKILLS_DIRECTORY: str = "skills"
PACKAGE_ROOT_AGENTS_DIRECTORY: str = "agents"
SKILL_MANIFEST_FILENAME: str = "SKILL.md"

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
FENCE_OPEN_PATTERN: str = r"^```([A-Za-z0-9_-]*)\s*$"
FENCE_CLOSE_PATTERN: str = r"^```\s*$"
BANNED_REASON_PREFIX: str = "banned_active_capability:"

UTF8_ENCODING: str = "utf-8"
NEWLINE_JOIN_SEPARATOR: str = "\n"