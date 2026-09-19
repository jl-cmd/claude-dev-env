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

# Capability names this package retired before the ever-shipped registry
# recorded them. Every other retired name resolves from that registry.
ALL_UNREGISTERED_RETIRED_CAPABILITY_NAMES: frozenset[str] = frozenset(
    {
        "stub-detector",
        "superpowers",
    }
)

EVER_SHIPPED_REGISTRY_RELATIVE_PATH: str = "bin/ever-shipped-skills.mjs"
EVER_SHIPPED_NAME_PATTERN: str = r"'([a-z][a-z0-9-]*)'"

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

SLASH_CAPABILITY_PATTERN: str = r"(?<![`\w./-])/([a-z][a-z0-9-]{2,})(?![\w/-])"
ALL_QUALIFIED_CAPABILITY_PATTERNS: tuple[str, ...] = (
    r"(?<![\w-])([a-z][a-z0-9-]{2,})/SKILL\.md",
    r"`skills/([a-z][a-z0-9-]{2,})`",
)
URL_PATTERN: str = r"\b[a-z][a-z0-9+.-]*://\S+"
MULTI_SEGMENT_PATH_PATTERN: str = r"(?<![\w-])[\w.{}-]*/[\w.{}/-]*/[\w.{}-]+"
BLANKED_SPAN: str = " "
FENCE_OPEN_PATTERN: str = r"^```([A-Za-z0-9_-]*)\s*$"
FENCE_CLOSE_PATTERN: str = r"^```\s*$"
RETIRED_REASON_PREFIX: str = "retired_capability:"

UTF8_ENCODING: str = "utf-8"
NEWLINE_JOIN_SEPARATOR: str = "\n"