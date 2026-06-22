"""Configuration constants for the duplicate_rmtree_helper_blocker PreToolUse hook."""

import re

PYTHON_FILE_EXTENSION: str = ".py"

HELPER_DEFINITION_PATTERN: re.Pattern[str] = re.compile(
    r"^[ \t]*def[ \t]+(?:_strip_read_only_and_retry|_force_remove_tree|force_rmtree)[ \t]*\(",
    re.MULTILINE,
)

ALL_EXEMPT_PATH_FRAGMENTS: tuple[str, ...] = (
    "windows_rmtree_blocker.py",
    "duplicate_rmtree_helper_blocker.py",
    "windows_safe_rmtree.py",
    "windows_filesystem.py",
)

ALL_EXEMPT_TEST_FILE_PREFIXES: tuple[str, ...] = ("test_",)
ALL_EXEMPT_TEST_FILE_SUFFIXES: tuple[str, ...] = ("_test.py",)
