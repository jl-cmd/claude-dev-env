"""Configuration constants for the PreToolUse hook stale_comment_reference_blocker."""

from re import Pattern, compile

COMMENT_IDENTIFIER_PATTERN: Pattern[str] = compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

ALL_COMMENT_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "not",
        "with",
        "from",
        "into",
        "onto",
        "out",
        "off",
        "this",
        "that",
        "these",
        "those",
        "each",
        "all",
        "any",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "its",
        "use",
        "uses",
        "used",
        "using",
        "when",
        "then",
        "than",
        "before",
        "after",
        "only",
        "also",
        "but",
        "per",
        "via",
        "one",
        "two",
        "new",
        "old",
        "now",
    }
)

PYTHON_FILE_SUFFIX: str = ".py"

COMMENT_LINE_PREFIX: str = "#"

STALE_COMMENT_DENY_TEMPLATE: str = (
    "The comment above the changed line in {file_path} names "
    "'{orphaned_name}'. Align it with the edited line's current name. The comment "
    "reads: {contradicted_comment}. Update the comment in the same edit to describe "
    "the edited line."
)

STALE_COMMENT_ADDITIONAL_CONTEXT: str = (
    "The comment directly above an edited line describes that line. Update it to "
    "describe the rewritten line. Keep the comment aligned with the line and make "
    "the change in the same Edit call."
)

STALE_COMMENT_SYSTEM_MESSAGE: str = (
    "Update the comment above the edited code line to describe the current line."
)
