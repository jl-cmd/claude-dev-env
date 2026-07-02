"""Constants for the stale_comment_reference_blocker PreToolUse hook.
"""

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

REPLACE_OPCODE_TAG: str = "replace"

STALE_COMMENT_DENY_TEMPLATE: str = (
    "The comment above the changed line in {file_path} names "
    "'{orphaned_name}', which this edit removes from the line below. "
    "The comment left in place reads: {contradicted_comment}. "
    "Update or remove the comment in the same edit."
)

STALE_COMMENT_ADDITIONAL_CONTEXT: str = (
    "A standalone comment directly above an edited line describes that "
    "line. When the edit drops a name the comment carries, rewrite the "
    "comment to describe the rewritten line, or delete the comment, inside "
    "the same Edit call."
)

STALE_COMMENT_SYSTEM_MESSAGE: str = (
    "Agent edited a code line without updating the comment above it that "
    "names what the edit removed"
)
