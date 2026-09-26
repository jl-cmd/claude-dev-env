"""Constants for the digest page check.

A digest page summarizes a set of changes for a reader who reads little and
needs to know every change. These values set the word budgets, the attribute
that marks one card, the elements that count as a picture, and the finding
messages.
"""

from __future__ import annotations

import re

UTF8_ENCODING: str = "utf-8"

CARD_WORD_BUDGET: int = 25

LEAD_WORD_BUDGET: int = 40

ALL_PICTURE_TAGS: frozenset[str] = frozenset({"img", "svg", "canvas", "picture"})

ALL_HIDDEN_TEXT_TAGS: frozenset[str] = frozenset(
    {"head", "script", "style", "template", "noscript"}
)

ALL_RAW_TEXT_TAGS: frozenset[str] = frozenset({"script", "style"})

ALL_VOID_TAGS: frozenset[str] = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)

MARKUP_PATTERN: re.Pattern[str] = re.compile(
    r"<!--.*?-->|<![^>]*>"
    r"|<(?P<closing>/?)(?P<tag_name>[a-zA-Z][\w:-]*)"
    r"(?P<attributes>(?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(?P<self_closing>/?)>",
    re.DOTALL,
)

CARD_ATTRIBUTE_PATTERN: re.Pattern[str] = re.compile(
    r"\bdata-digest-card\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)')"
)

WORD_PATTERN: re.Pattern[str] = re.compile(r"[^\W_][\w'’-]*")

MISSING_CARD_FINDING: str = "missing card {card_id}: the page leaves it out"

DUPLICATE_CARD_FINDING: str = "card {card_id} appears {count} times"

CARD_OVER_BUDGET_FINDING: str = (
    "card {card_id} carries {word_count} words; the budget is {budget}"
)

CARD_WITHOUT_PICTURE_FINDING: str = "card {card_id} has no picture"

LEAD_OVER_BUDGET_FINDING: str = (
    "text outside the cards carries {word_count} words; the budget is {budget}"
)

CLEAN_VERDICT: str = "CLEAN: {card_count} cards, every one present"

EXIT_CLEAN: int = 0

EXIT_FINDINGS: int = 1
