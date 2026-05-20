"""Constants for the inline-tuple snake_case-string-magic check in code_rules_enforcer.

Mirrors the column-name/key heuristic previously held only in
``_shared/pr-loop/scripts/code_rules_gate.py`` so the Write/Edit hook can
catch the same pattern that the commit-time gate caught.
"""

EXPECTED_TUPLE_PAIR_LENGTH: int = 2

MAX_INLINE_TUPLE_STRING_MAGIC_ISSUES: int = 3

MINIMUM_SNAKE_CASE_LENGTH_AFTER_FIRST_CHAR: int = 2

SNAKE_CASE_LITERAL_PATTERN: str = (
    r"^[a-z][a-z0-9_]{" + str(MINIMUM_SNAKE_CASE_LENGTH_AFTER_FIRST_CHAR) + r",}$"
)

ALL_SNAKE_CASE_KEYWORD_EXEMPTIONS: frozenset[str] = frozenset(
    {"true", "false", "none", "null"}
)

INLINE_TUPLE_STRING_MAGIC_MESSAGE_SUFFIX: str = "extract to config"
