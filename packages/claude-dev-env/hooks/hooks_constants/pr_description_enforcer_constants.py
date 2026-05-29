"""Configuration constants for the pr_description_enforcer PreToolUse hook."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


_PLUGIN_ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PR_GUIDE_PATH: str = os.path.join(_PLUGIN_ROOT, "docs", "PR_DESCRIPTION_GUIDE.md")

MINIMUM_SUBSTANTIVE_PROSE_CHARS: int = 40

FENCED_CODE_BLOCK_PATTERN: re.Pattern[str] = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_PATTERN: re.Pattern[str] = re.compile(r"`[^`]*`")
HEADING_LINE_PATTERN: re.Pattern[str] = re.compile(r"^#+[ \t].*$", re.MULTILINE)
BOLD_PAIR_PATTERN: re.Pattern[str] = re.compile(r"\*\*([^*]+?)\*\*")
BULLET_MARKER_PATTERN: re.Pattern[str] = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
BLOCKQUOTE_MARKER_PATTERN: re.Pattern[str] = re.compile(r"^\s*>\s+", re.MULTILINE)
BLOCKQUOTE_LINE_PATTERN: re.Pattern[str] = re.compile(r"^\s*>.*$", re.MULTILINE)
TABLE_ROW_LINE_PATTERN: re.Pattern[str] = re.compile(r"^\s*\|.*\|.*$", re.MULTILINE)
LINK_TEXT_PATTERN: re.Pattern[str] = re.compile(r"\[([^\]]+)\]\([^)]+\)")
WHITESPACE_RUN_PATTERN: re.Pattern[str] = re.compile(r"\s+")

SUMMARY_HEADER: str = "## Summary"
PROBLEM_HEADER: str = "## Problem"
TEST_PLAN_HEADER: str = "## Test plan"
TESTS_HEADER: str = "## Tests"
TESTING_HEADER: str = "## Testing"
VERIFICATION_HEADER: str = "## Verification"
VALIDATION_HEADER: str = "## Validation"

ALL_HEAVY_OPENING_HEADERS: frozenset[str] = frozenset({PROBLEM_HEADER, SUMMARY_HEADER})
ALL_HEAVY_TESTING_HEADERS: frozenset[str] = frozenset(
    {TEST_PLAN_HEADER, TESTING_HEADER, TESTS_HEADER, VERIFICATION_HEADER, VALIDATION_HEADER}
)
GH_PR_COMMAND_MIN_TOKEN_COUNT: int = 3
ATOMIC_WRITE_TEMP_SUFFIX: str = ".tmp"
SELF_CLOSING_REFERENCE_MESSAGE_PREFIX: str = "PR body references its own PR number #"
SELF_CLOSING_REFERENCE_MESSAGE_SUFFIX: str = (
    " as a self-closing keyword (Fixes/Closes/Resolves) -- remove the self-reference"
)

SELF_REFERENCE_PATTERN_TEMPLATE: str = (
    r"\b(?:Close|Closes|Closed|Fix|Fixes|Fixed|Resolve|Resolves|Resolved)"
    r"\s+#{pr_number}\b"
)

THIS_PR_OPENING_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*(?:#[^\n]*\n\s*)*This PR\b",
    re.IGNORECASE,
)

TRIVIAL_SHAPE: str = "trivial"
STANDARD_SHAPE: str = "standard"
HEAVY_SHAPE: str = "heavy"

TRIVIAL_BODY_CHAR_THRESHOLD: int = 200
HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION: int = 500

READABILITY_MAX_SENTENCE_WORDS: int = 28
READABILITY_AVG_SENTENCE_WORDS: int = 18
READABILITY_MIN_FLESCH: int = 50
READABILITY_STRIKE_THRESHOLD: int = 3

READABILITY_LOOSEN_CAP: int = 3
READABILITY_MIN_FLESCH_FLOOR: int = 30
READABILITY_MAX_SENTENCE_WORDS_CEILING: int = 60
READABILITY_AVG_SENTENCE_WORDS_CEILING: int = 40

READABILITY_FLESCH_LOOSEN_FACTOR: float = 0.9
READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR: float = 10 / 9

ALL_READABILITY_CLI_FLAG_TOKENS: frozenset[str] = frozenset(
    {
        "--readability-loosen",
        "--readability-reset",
        "--readability-disable",
        "--readability-enable",
    }
)

FLESCH_BASE_SCORE: float = 206.835
FLESCH_WORDS_PER_SENTENCE_COEFFICIENT: float = 1.015
FLESCH_SYLLABLES_PER_WORD_COEFFICIENT: float = 84.6
FLESCH_PERFECT_SCORE: float = 100.0

READABILITY_STATE_FILE: Path = Path.home() / ".claude" / "state" / "pr_description_readability_strikes.json"
READABILITY_THRESHOLD_OVERRIDE_FILE: Path = (
    Path.home() / ".claude" / "state" / "pr_description_readability_overrides.json"
)
READABILITY_ENABLED_STATE_FILE: Path = (
    Path.home() / ".claude" / "state" / "pr_description_readability_enabled.json"
)


@dataclass(frozen=True)
class ReadabilityThresholds:
    """Three readability thresholds carried as a single typed structure."""

    flesch_min: int
    max_sentence_words: int
    avg_sentence_words: int


DEFAULT_READABILITY_THRESHOLDS: ReadabilityThresholds = ReadabilityThresholds(
    flesch_min=READABILITY_MIN_FLESCH,
    max_sentence_words=READABILITY_MAX_SENTENCE_WORDS,
    avg_sentence_words=READABILITY_AVG_SENTENCE_WORDS,
)


__all__ = [
    "ALL_HEAVY_OPENING_HEADERS",
    "ALL_HEAVY_TESTING_HEADERS",
    "ALL_READABILITY_CLI_FLAG_TOKENS",
    "ATOMIC_WRITE_TEMP_SUFFIX",
    "BLOCKQUOTE_LINE_PATTERN",
    "BLOCKQUOTE_MARKER_PATTERN",
    "BOLD_PAIR_PATTERN",
    "BULLET_MARKER_PATTERN",
    "DEFAULT_READABILITY_THRESHOLDS",
    "FENCED_CODE_BLOCK_PATTERN",
    "FLESCH_BASE_SCORE",
    "FLESCH_PERFECT_SCORE",
    "FLESCH_SYLLABLES_PER_WORD_COEFFICIENT",
    "FLESCH_WORDS_PER_SENTENCE_COEFFICIENT",
    "GH_PR_COMMAND_MIN_TOKEN_COUNT",
    "HEADING_LINE_PATTERN",
    "HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION",
    "HEAVY_SHAPE",
    "INLINE_CODE_PATTERN",
    "LINK_TEXT_PATTERN",
    "MINIMUM_SUBSTANTIVE_PROSE_CHARS",
    "PR_GUIDE_PATH",
    "READABILITY_AVG_SENTENCE_WORDS_CEILING",
    "READABILITY_ENABLED_STATE_FILE",
    "READABILITY_FLESCH_LOOSEN_FACTOR",
    "READABILITY_LOOSEN_CAP",
    "READABILITY_MAX_SENTENCE_WORDS_CEILING",
    "READABILITY_MIN_FLESCH_FLOOR",
    "READABILITY_SENTENCE_WORDS_LOOSEN_FACTOR",
    "READABILITY_STATE_FILE",
    "READABILITY_STRIKE_THRESHOLD",
    "READABILITY_THRESHOLD_OVERRIDE_FILE",
    "ReadabilityThresholds",
    "SELF_CLOSING_REFERENCE_MESSAGE_PREFIX",
    "SELF_CLOSING_REFERENCE_MESSAGE_SUFFIX",
    "SELF_REFERENCE_PATTERN_TEMPLATE",
    "STANDARD_SHAPE",
    "TABLE_ROW_LINE_PATTERN",
    "THIS_PR_OPENING_PATTERN",
    "TRIVIAL_BODY_CHAR_THRESHOLD",
    "TRIVIAL_SHAPE",
    "WHITESPACE_RUN_PATTERN",
]
