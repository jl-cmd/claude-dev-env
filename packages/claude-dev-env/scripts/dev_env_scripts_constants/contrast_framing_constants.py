"""Constants for the contrast-framing detector.

Each form names one shape a sentence takes when it defines its subject
against a rejected reading::

    "a diff regression, not shared code"   -> trailing-comma-not
    "park it rather than fix it"           -> substitution-rather-than
    "precision matters more than coverage" -> comparative-ranking
    ok: "the function runs more than 30 lines"

The rule file ``rules/no-contrast-framing.md`` carries one row for each name
here, and a test holds the two in step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ContrastFramingForm:
    """One banned contrast form and the pattern that finds it."""

    name: str
    pattern: re.Pattern[str]
    guidance: str


ALL_CONTRAST_FRAMING_FORMS: tuple[ContrastFramingForm, ...] = (
    ContrastFramingForm(
        "trailing-comma-not",
        re.compile(r",\s+not\s+[\w\"'`(]", re.IGNORECASE),
        "Drop the clause after the comma and state what is true.",
    ),
    ContrastFramingForm(
        "corrective-it-is-not",
        re.compile(
            r"\b(?:it|that|this)(?:'s|\s+is|\s+was)\s+not\b[^.!?]*?,\s*"
            r"(?:it|that|this)(?:'s|\s+is|\s+was)\b",
            re.IGNORECASE,
        ),
        "State what it is and leave the rejected reading out.",
    ),
    ContrastFramingForm(
        "substitution-rather-than",
        re.compile(r"\brather than\b", re.IGNORECASE),
        "Name the thing you chose and stop.",
    ),
    ContrastFramingForm(
        "additive-not-just",
        re.compile(r"\bnot (?:just|only|merely|simply)\b", re.IGNORECASE),
        "Say the point the sentence is building toward.",
    ),
    ContrastFramingForm(
        "comparative-ranking",
        re.compile(
            r"\b(?:matters?|counts?|helps?|weighs?)\s+more\s+than\b"
            r"|\bless\s+(?:important|useful|valuable)\s+than\b"
            r"|\bmore\s+(?:important|useful|valuable)\s+than\b"
            r"|\bmore\s+than\s+(?:trying|attempting|hoping)\b",
            re.IGNORECASE,
        ),
        "State the thing you want. Leave the ranking out.",
    ),
    ContrastFramingForm(
        "substitution-as-opposed-to",
        re.compile(r"\bas opposed to\b", re.IGNORECASE),
        "Name the thing you chose and stop.",
    ),
)

CONTRAST_FRAMING_MESSAGE_TEMPLATE: str = (
    'Contrast framing ({name}): "{text}". {guidance}'
)

CONTRAST_FRAMING_QUOTED_LINE_LIMIT: int = 120

CONTRAST_FRAMING_FINDING_CODE: str = "contrast-framing"

CONTRAST_FRAMING_RULE_DOCUMENT: str = "rules/no-contrast-framing.md"
