"""Configuration constants for the banned-identifier check in code_rules_enforcer."""

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
MAX_BANNED_IDENTIFIER_ISSUES: int = 3
BANNED_IDENTIFIER_MESSAGE_SUFFIX: str = (
    "use descriptive name (see CODE_RULES Naming section)"
)
BANNED_IDENTIFIER_SKIP_ADVISORY: str = (
    "banned-identifier check skipped: file did not parse as Python"
)
