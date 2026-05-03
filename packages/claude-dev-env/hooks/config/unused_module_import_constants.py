"""Constants for the unused module-level import scan in ``code_rules_enforcer``."""

MAX_UNUSED_IMPORT_ISSUES: int = 25
UNUSED_IMPORT_GUIDANCE: str = (
    "remove unused import; if kept for side effects, mark with `# noqa: F401`"
)
TYPE_CHECKING_IDENTIFIER: str = "TYPE_CHECKING"
