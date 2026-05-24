"""Configuration constants for the banned-identifier check in code_rules_enforcer."""

import re

ALL_BANNED_IDENTIFIERS: frozenset[str] = frozenset(
    {
        "result",
        "data",
        "output",
        "response",
        "value",
        "item",
        "temp",
        "tmp",
        "argv",
        "args",
        "kwargs",
        "argc",
        "rc",
        "cfg",
        "ctx",
        "cnt",
        "btn",
        "idx",
        "tmp",
        "msg",
        "elem",
        "val",
    }
)
ALL_BANNED_NOUN_WORDS: frozenset[str] = frozenset(
    {
        "result", "results",
        "data",
        "output", "outputs",
        "response", "responses",
        "value", "values",
        "item", "items",
        "temp",
    }
)
CAMEL_CASE_WORD_PATTERN: re.Pattern[str] = re.compile(
    r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+"
)
MAX_BANNED_IDENTIFIER_ISSUES: int = 3
BANNED_IDENTIFIER_MESSAGE_SUFFIX: str = (
    "use descriptive name (see CODE_RULES Naming section)"
)
BANNED_NOUN_WORD_MESSAGE_SUFFIX: str = (
    "contains banned noun word - rename to a domain-specific term (see CODE_RULES §5)"
)
BANNED_IDENTIFIER_SKIP_ADVISORY: str = (
    "banned-identifier check skipped: file did not parse as Python"
)
