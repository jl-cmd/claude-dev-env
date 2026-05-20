"""Configuration constants for the bugteam CODE_RULES gate script."""

from __future__ import annotations

BUGTEAM_CODE_RULES_GATE_PREFIX: str = "bugteam_code_rules_gate: "
EXIT_CODE_ENFORCER_MISSING: int = 2
HUNK_HEADER_RAW_PATTERN: str = r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@"
MAXIMUM_ISSUES_TO_REPORT: int = 3
MAXIMUM_COLUMN_TUPLE_ELEMENT_COUNT: int = 2
VIOLATION_LINE_RAW_PATTERN: str = r"^Line (\d+):"

ALL_CODE_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".js", ".ts", ".tsx", ".jsx"}
)
ALL_JS_FILE_EXTENSIONS: tuple[str, ...] = (".js", ".ts", ".tsx", ".jsx")
ALL_COLUMN_MAGIC_FALSE_VALUES: frozenset[str] = frozenset(
    {"true", "false", "none", "null"}
)
ALL_GIT_DIFF_CACHED_ARGS: tuple[str, ...] = (
    "git",
    "diff",
    "--cached",
    "--name-only",
    "-z",
)
