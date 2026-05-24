"""Configuration constants for the bugteam CODE_RULES gate script."""

from __future__ import annotations

import re

BUGTEAM_CODE_RULES_GATE_PREFIX: str = "bugteam_code_rules_gate: "
EXIT_CODE_ENFORCER_MISSING: int = 2
HUNK_HEADER_RAW_PATTERN: str = r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@"
MAXIMUM_ISSUES_TO_REPORT: int = 3
MAX_VIOLATIONS_PER_CHECK: int = 3
MAXIMUM_COLUMN_TUPLE_ELEMENT_COUNT: int = 2
PYTHON_FILE_EXTENSION: str = ".py"
VIOLATION_LINE_RAW_PATTERN: str = r"^Line (\d+):"

FUNCTION_LENGTH_VIOLATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(defined at line (\d+)\) is (\d+) lines"
)
FUNCTION_LENGTH_DEFINITION_LINE_GROUP_INDEX: int = 1
FUNCTION_LENGTH_SPAN_GROUP_INDEX: int = 2

ISOLATION_VIOLATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(defined at line (\d+), spanning (\d+) lines\)"
)
ISOLATION_DEFINITION_LINE_GROUP_INDEX: int = 1
ISOLATION_SPAN_GROUP_INDEX: int = 2

BANNED_NOUN_VIOLATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(binding span at line (\d+), spanning (\d+) lines\)"
)
BANNED_NOUN_DEFINITION_LINE_GROUP_INDEX: int = 1
BANNED_NOUN_SPAN_GROUP_INDEX: int = 2

ALL_CODE_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".js", ".ts", ".tsx", ".jsx"}
)
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
