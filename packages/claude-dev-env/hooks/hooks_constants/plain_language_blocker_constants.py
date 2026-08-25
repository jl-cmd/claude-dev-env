"""Configuration for the AskUserQuestion plain-language blocker."""

from __future__ import annotations

import re

ALL_PLAIN_LANGUAGE_TERM_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\butilize\b", re.IGNORECASE), "use"),
    (re.compile(r"\binitiate\b", re.IGNORECASE), "start"),
    (re.compile(r"\bsufficient\b", re.IGNORECASE), "enough"),
    (re.compile(r"\bprior to\b", re.IGNORECASE), "before"),
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
)

FENCED_CODE_PATTERN = re.compile(r"```[\s\S]*?```")
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")
URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
FILE_PATH_PATTERN = re.compile(
    r"(?<!\w)(?:[A-Za-z]:[\\/]|\.\.?[\\/])?[\w.-]+(?:[\\/][\w.-]+)+"
)

PLAIN_LANGUAGE_BLOCK_PREFIX = "BLOCKED: [PLAIN_LANGUAGE] Use familiar words: "
PLAIN_LANGUAGE_TERM_SEPARATOR = "; "
PLAIN_LANGUAGE_NOTICE = (
    "Plain-language check: use familiar words in the question and its options."
)
