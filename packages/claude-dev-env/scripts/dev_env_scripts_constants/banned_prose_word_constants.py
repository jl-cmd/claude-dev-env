"""Constants for the banned-prose-word detector.

The package AGENTS.md bans a family of emphasis words from every authored
surface. These patterns describe where the ban applies and which spans of a
document are code rather than prose.
"""

from __future__ import annotations

import re

UTF8_ENCODING: str = "utf-8"

ALL_GOVERNED_PATH_SEGMENTS: tuple[str, ...] = (
    "/.agents/agents/",
    "/.agents/skills/",
    "/audit-rubrics/",
    "/commands/",
    "/docs/",
    "/output-styles/",
    "/rules/",
    "/system-prompts/",
)

ALL_EXEMPT_PATH_SEGMENTS: tuple[str, ...] = (
    "-archived/",
    "/fixtures/",
    "/tests/",
    "/changelog.md",
)

ALL_GOVERNED_SUFFIXES: frozenset[str] = frozenset({".md", ".mdx", ".xml"})

ALL_BANNED_PROSE_WORDS: tuple[str, ...] = (
    "real",
    "really",
    "real-world",
    "actual",
    "actually",
    "genuine",
    "genuinely",
    "truly",
)

BANNED_PROSE_WORD_PATTERN: re.Pattern[str] = re.compile(
    r"(?<![\w-])(" + "|".join(ALL_BANNED_PROSE_WORDS) + r")(?![\w-])",
    re.IGNORECASE,
)

ADJECTIVAL_TRUE_PATTERN: re.Pattern[str] = re.compile(
    r"(?<![\w-])true(?![\w-])\s+[a-z]", re.IGNORECASE
)

ALL_PREDICATIVE_TRUE_LEADS: frozenset[str] = frozenset(
    {
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "always",
        "still",
        "holds",
        "hold",
        "held",
        "stays",
        "stay",
        "remains",
        "remain",
        "returns",
        "return",
        "reads",
        "read",
        "and",
        "or",
        "not",
        "never",
    }
)

FENCED_CODE_PATTERN: re.Pattern[str] = re.compile(r"^\s*```")
INDENTED_CODE_PATTERN: re.Pattern[str] = re.compile(r"^(?: {4,}|\t)\S")
INLINE_CODE_PATTERN: re.Pattern[str] = re.compile(r"`[^`]*`")
URL_PATTERN: re.Pattern[str] = re.compile(r"\b(?:https?|file)://\S+")
PATH_PATTERN: re.Pattern[str] = re.compile(r"(?<![\w])[\w./-]*/[\w./-]+")
MARKDOWN_LINK_TARGET_PATTERN: re.Pattern[str] = re.compile(r"\]\([^)]*\)")
XML_TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]+>")
BLANKED_SPAN: str = " "

BANNED_PROSE_WORD_RULE_ID: str = "banned-prose-word"
BANNED_PROSE_WORD_MESSAGE: str = (
    "Banned word: {word}. Delete it and name the evidence instead."
)
