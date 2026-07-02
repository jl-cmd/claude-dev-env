"""Configuration constants for the JavaScript convention checks in code_rules_enforcer."""

import re

ALL_JAVASCRIPT_BANNED_IDENTIFIERS: frozenset[str] = frozenset(
    {
        "result",
        "data",
        "output",
        "response",
        "value",
        "item",
        "temp",
        "ctx",
        "cfg",
        "msg",
        "btn",
        "idx",
        "cnt",
        "tmp",
        "elem",
        "val",
    }
)

_JAVASCRIPT_NEGATION_OPERAND: str = (
    r"[A-Za-z_$][\w$]*"
    r"(?:\s*\.\s*[A-Za-z_$][\w$]*|\s*\((?:[^()]|\([^()]*\))*\))*"
)

JAVASCRIPT_BOOLEAN_DECLARATION_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:(?:true|false)\b|!\s*" + _JAVASCRIPT_NEGATION_OPERAND + r"\s*(?:;|$))"
)

JAVASCRIPT_BOOLEAN_JSDOC_PARAMETER_PATTERN: re.Pattern[str] = re.compile(
    r"@param\s*\{\s*boolean\s*\}\s+(?P<name>[A-Za-z_$][\w$]*)"
)

JAVASCRIPT_DECLARATION_NAME_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*="
)

JAVASCRIPT_BOOLEAN_PREFIX_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:is|has|should|can|was|did)(?:[A-Z0-9_]|$)"
)

BOOLEAN_PREFIX_GUIDANCE: str = "prefix with is/has/should/can/was/did"

SINGLE_CHARACTER_NAME_LENGTH: int = 1

MAX_JAVASCRIPT_BOOLEAN_NAMING_ISSUES: int = 20

MAX_JAVASCRIPT_BANNED_IDENTIFIER_ISSUES: int = 20
