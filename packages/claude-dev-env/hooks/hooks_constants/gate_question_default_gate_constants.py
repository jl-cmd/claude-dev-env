"""Constants for the gate_question_default_gate PreToolUse hook.

Holds the tool name, payload keys, the tight gate-question trigger patterns, the
refactor-to-pass label pattern and recommended marker, and the deny text.
"""

from __future__ import annotations

import re

ASK_USER_QUESTION_TOOL_NAME = "AskUserQuestion"

QUESTIONS_PAYLOAD_KEY = "questions"
QUESTION_TEXT_KEY = "question"
OPTIONS_KEY = "options"
OPTION_LABEL_KEY = "label"

GATE_TRIGGER_REQUIRED_PATTERN = re.compile(r"\bgate\b", re.IGNORECASE)
GATE_TRIGGER_SUPPORTING_PATTERN = re.compile(
    r"\b(?:block|blocked|deny|denied|refactor|violation|code_rules)\b",
    re.IGNORECASE,
)

REFACTOR_TO_PASS_LABEL_PATTERN = re.compile(r"refactor\b.*\bpass\b.*\bgate\b", re.IGNORECASE)
RECOMMENDED_LABEL_MARKER = "recommended"
PROSE_JOIN_SEPARATOR = "\n"

GATE_QUESTION_DENY_MESSAGE = (
    "BLOCKED: [GATE_DEFAULT] This question is about a gate-blocked edit. "
    'List "Refactor to pass the gate (Recommended)" as the first choice, so '
    "the default is to fix the code until the gate passes. A skip token stays a "
    "last resort the user approves."
)

GATE_QUESTION_USER_NOTICE = (
    "Refactor to pass the gate is the first, recommended choice for a gate-blocked edit."
)
