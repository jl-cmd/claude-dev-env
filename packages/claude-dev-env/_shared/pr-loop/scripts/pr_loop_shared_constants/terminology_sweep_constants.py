"""Constants for the commit-time terminology sweep."""

import re

ALL_SWEEP_CODE_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".mjs", ".js", ".ts"}
)

MARKDOWN_FILE_EXTENSION: str = ".md"

SNAKE_CASE_IDENTIFIER_PATTERN: re.Pattern[str] = re.compile(
    r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"
)

CAMEL_CASE_IDENTIFIER_PATTERN: re.Pattern[str] = re.compile(
    r"\b[a-z]+(?:[A-Z][a-z0-9]*)+\b"
)

CAMEL_CASE_WORD_PATTERN: re.Pattern[str] = re.compile(
    r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+"
)

HYPHENATED_PROSE_TOKEN_PATTERN: re.Pattern[str] = re.compile(
    r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z][A-Za-z0-9]*)+\b"
)

PROSE_WORD_PATTERN: re.Pattern[str] = re.compile(r"[A-Za-z][A-Za-z0-9]*")

STRING_LITERAL_CONTENT_PATTERN: re.Pattern[str] = re.compile(
    r"\"([^\"]*)\"|'([^']*)'|`([^`]*)`"
)

DIFF_FILE_HEADER_PREFIX: str = "+++ "

DIFF_HUNK_HEADER_PATTERN: re.Pattern[str] = re.compile(
    r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@"
)

DIFF_ADDED_LINE_PREFIX: str = "+"

DIFF_REMOVED_LINE_PREFIX: str = "-"

DIFF_NEW_FILE_HEADER_PREFIX: str = "+++"

DIFF_OLD_FILE_HEADER_PREFIX: str = "---"

ALL_DIFF_FILE_PATH_STRIP_PREFIXES: tuple[str, ...] = ("a/", "b/")

PYTHON_COMMENT_MARKER: str = "#"

JAVASCRIPT_LINE_COMMENT_MARKER: str = "//"

JSDOC_CONTINUATION_MARKER: str = "*"

MINIMUM_IDENTIFIER_TOKEN_COUNT: int = 2

ALL_COMMON_ENGLISH_COMPOUND_TAIL_WORDS: frozenset[str] = frozenset(
    {
        "only",
        "driven",
        "safe",
        "based",
        "level",
        "quality",
        "known",
        "source",
        "party",
        "case",
        "time",
        "wide",
        "free",
        "friendly",
        "specific",
        "aware",
        "ready",
        "side",
        "grade",
        "oriented",
        "related",
        "sensitive",
        "facing",
    }
)

TERMINOLOGY_FINDING_TEMPLATE: str = (
    "{file_path}:{line_number}: prose term '{candidate}' near-misses code "
    "identifier '{identifier}' (shared prefix token, divergent tail) — align "
    "the prose wording with the identifier"
)

TERMINOLOGY_SWEEP_DESCRIPTION: str = (
    "Flag prose terms that near-miss an identifier introduced on added code "
    "lines of a unified diff."
)

DIFF_FILE_ARGUMENT_HELP: str = (
    "Read the unified diff from this file instead of standard input."
)


ALL_GIT_DIFF_CACHED_UNIFIED_ZERO_COMMAND: tuple[str, ...] = (
    "git",
    "diff",
    "--cached",
    "--unified=0",
)

GIT_DIFF_SUBPROCESS_TIMEOUT_SECONDS: int = 30

TERMINOLOGY_SWEEP_GATE_HEADER: str = (
    "terminology_sweep: {finding_count} cross-surface terminology near-miss(es) "
    "on staged prose:"
)
