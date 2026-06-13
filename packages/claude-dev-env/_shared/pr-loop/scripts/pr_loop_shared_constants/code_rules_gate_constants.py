"""Constants for code_rules_gate.py per CODE_RULES centralized-config rule."""

import re

MAX_VIOLATIONS_PER_CHECK: int = 3
EXPECTED_TUPLE_PAIR_LENGTH: int = 2

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

DUPLICATE_BODY_VIOLATION_PATTERN: re.Pattern[str] = re.compile(
    r"\(duplicate body span at line (\d+), spanning (\d+) lines\)"
)
DUPLICATE_BODY_DEFINITION_LINE_GROUP_INDEX: int = 1
DUPLICATE_BODY_SPAN_GROUP_INDEX: int = 2

ALL_CODE_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".js", ".ts", ".tsx", ".jsx"}
)

ALL_LITERAL_KEYWORD_EXEMPTIONS: frozenset[str] = frozenset(
    {"true", "false", "none", "null"}
)

CONFIG_PATH_SEGMENT: str = "/config/"

TESTS_PATH_SEGMENT: str = "/tests/"

ALL_TEST_FILENAME_SUFFIXES: tuple[str, ...] = ("_test.py",)

ALL_TEST_FILENAME_GLOB_SUFFIXES: tuple[str, ...] = (
    ".test.",
    ".spec.",
)

TEST_CONFTEST_FILENAME: str = "conftest.py"

TEST_FILENAME_PREFIX: str = "test_"

MINIMUM_COLUMN_NAME_LENGTH_AFTER_FIRST_CHAR: int = 2

COLUMN_KEY_PATTERN_TEMPLATE: str = r"^[a-z][a-z0-9_]{{{minimum_length},}}$"

GIT_NAME_STATUS_ADDED_PREFIX: str = "A"

GIT_NAME_STATUS_RENAMED_PREFIX: str = "R"

EXPECTED_RENAME_COLUMN_COUNT: int = 3

EXPECTED_NON_RENAME_COLUMN_COUNT: int = 2

PYTHON_FILE_EXTENSION: str = ".py"

ALL_GIT_DIFF_CACHED_NAME_ONLY_NULL_TERMINATED_COMMAND: tuple[str, ...] = (
    "git",
    "diff",
    "--cached",
    "--name-only",
    "-z",
)

ALL_GIT_DIFF_NAME_ONLY_NULL_TERMINATED_COMMAND_PREFIX: tuple[str, ...] = (
    "git",
    "diff",
    "--name-only",
    "-z",
)
