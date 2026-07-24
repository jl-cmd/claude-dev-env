"""Configuration constants for ask_user_question_style_blocker PreToolUse hook."""

from __future__ import annotations

import re

TOOL_NAME: str = "AskUserQuestion"
HOOK_EVENT_NAME: str = "PreToolUse"
DENY_DECISION: str = "deny"
CALLING_HOOK_NAME: str = "ask_user_question_style_blocker.py"

PLAIN_BRIEF_STYLE_PATH: str = "output-styles/plain-brief.md"
NEWLINE_JOIN_SEPARATOR: str = "\n"

# Shortest grounded prefix before the first "?" that still reads as a fact.
MINIMUM_CONTEXT_PREFIX_CHARACTER_COUNT: int = 12

# Plain-brief hard length caps applied to AskUserQuestion prose.
MAXIMUM_WORDS_PER_SENTENCE: int = 28
MAXIMUM_SENTENCES_PER_QUESTION: int = 3
MAXIMUM_SENTENCES_PER_OPTION_DESCRIPTION: int = 2

# Colon / em-dash clause separators (always statement boundaries).
CLAUSE_SEPARATOR_PATTERN: re.Pattern[str] = re.compile(r":\s+|[—–]\s+")

# Period / exclamation / question followed by whitespace (candidate sentence end).
TERMINATOR_WITH_SPACE_PATTERN: re.Pattern[str] = re.compile(r"[.!?]\s+")

# Last token immediately before a terminator (word or acronym).
TOKEN_BEFORE_TERMINATOR_PATTERN: re.Pattern[str] = re.compile(r"([A-Za-z0-9]+)\s*\Z")

# Always suppress these forms before a capital (``Dr. Smith``, ``St. Louis``).
ALL_TITLE_PERIOD_ABBREVIATIONS: frozenset[str] = frozenset(
    {
        "dr",
        "mr",
        "mrs",
        "ms",
        "jr",
        "sr",
        "st",
        "ave",
        "vs",
    }
)

# Suppress only when the next non-space is not a sentence start (``etc. more``).
# When the next token is capital (``etc. How`` / ``Inc. Which``), treat as a real end.
ALL_SOFT_PERIOD_ABBREVIATIONS: frozenset[str] = frozenset(
    {
        "etc",
        "eg",
        "ie",
        "inc",
        "ltd",
        "dept",
        "est",
        "approx",
    }
)

# Process-narration openers banned by plain-brief rule 1 (one scan per prose blob).
PROCESS_NARRATION_OPENER_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:"
    r"I\s+looked\s+at|"
    r"First,\s+I|"
    r"I\s+found|"
    r"After\s+reviewing|"
    r"I\s+checked|"
    r"Looking\s+at|"
    r"Having\s+reviewed|"
    r"I\s+investigated|"
    r"I\s+examined|"
    r"Upon\s+reviewing|"
    r"I\s+noticed|"
    r"When\s+I\s+looked|"
    r"I\s+reviewed|"
    r"After\s+looking"
    r")\b",
    re.IGNORECASE,
)

ARROW_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"→|->")
MINIMUM_ARROW_TOKENS_FOR_CHAIN: int = 2

# Three consecutive hyphenated tokens, e.g. "hash-bound fail-closed release-gate".
STACKED_HYPHEN_COMPOUND_PATTERN: re.Pattern[str] = re.compile(
    r"\b[A-Za-z]+-[A-Za-z]+(?:\s+[A-Za-z]+-[A-Za-z]+){2,}\b"
)

FINDING_MISSING_CONTEXT: str = "missing_context_before_question"
FINDING_MISSING_OPTION_DESCRIPTION: str = "missing_option_description"
FINDING_PROCESS_NARRATION: str = "process_narration_opener"
FINDING_ARROW_CHAIN: str = "arrow_chain"
FINDING_STACKED_HYPHEN_COMPOUND: str = "stacked_hyphen_compound"
FINDING_LONG_SENTENCE: str = "long_sentence"
FINDING_TOO_MANY_SENTENCES: str = "too_many_sentences"

USER_FACING_NOTICE: str = (
    "AskUserQuestion style: put a short fact before the question, and keep the "
    "wording plain-brief (short active sentences, outcome first)."
)

CORRECTIVE_MESSAGE_HEADER: str = (
    "BLOCKED: [ASK_USER_QUESTION_STYLE] AskUserQuestion prose failed the "
    "context-before-question and plain-brief wording checks."
)

CORRECTIVE_MESSAGE_FOOTER: str = (
    "Rewrite the call so each question leads with a short fact sentence "
    "(what you found or what is at stake), then the question. Write every "
    "question and option description in plain-brief style: lead with the "
    "outcome, one idea per short sentence, no process narration, no arrow "
    f"chains, no stacked-hyphen jargon. See `{PLAIN_BRIEF_STYLE_PATH}`."
)

ALL_FINDING_GUIDANCE_BY_CODE: dict[str, str] = {
    FINDING_MISSING_CONTEXT: (
        "Put a short fact sentence before the question "
        '(example: "The gate blocks bare rm on worktrees. How should temp cleanup run?").'
    ),
    FINDING_MISSING_OPTION_DESCRIPTION: (
        "Give every option a short description so the user knows what choosing it does."
    ),
    FINDING_PROCESS_NARRATION: (
        'Open with the outcome or fact, not process narration ("I looked at...", "First, I...").'
    ),
    FINDING_ARROW_CHAIN: (
        'Drop arrow chains ("A → B → fails"); write the path in short sentences.'
    ),
    FINDING_STACKED_HYPHEN_COMPOUND: (
        "Unpack stacked-hyphen jargon into plain words on first use."
    ),
    FINDING_LONG_SENTENCE: (
        f"Keep each sentence at {MAXIMUM_WORDS_PER_SENTENCE} words or fewer; split long ones."
    ),
    FINDING_TOO_MANY_SENTENCES: (
        f"Keep the question field to {MAXIMUM_SENTENCES_PER_QUESTION} sentences or fewer, "
        f"and each option description to {MAXIMUM_SENTENCES_PER_OPTION_DESCRIPTION} or fewer."
    ),
}
