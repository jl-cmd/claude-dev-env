"""Constants for the public-function paired-test coverage check in ``code_rules_enforcer``.

Lives under the hooks-tree ``hooks_constants`` package so its module-level
UPPER_SNAKE constants satisfy the CODE_RULES "constants live in config"
requirement and share a home with the other hook-tree configuration.
"""

from __future__ import annotations


PYTHON_SOURCE_SUFFIX: str = ".py"
TESTS_DIRECTORY_NAME: str = "tests"
INIT_MODULE_FILENAME: str = "__init__.py"
STEM_TEST_FILENAME_PREFIX: str = "test_"
STEM_TEST_FILENAME_SUFFIX: str = "_test.py"
ALL_TEST_FILENAME_GLOBS: tuple[str, ...] = ("test_*.py", "*_test.py")
EXEMPT_PUBLIC_FUNCTION_NAMES: frozenset[str] = frozenset({"main"})
ANCESTOR_DIRECTORY_WALK_LIMIT: int = 10
MAX_TEST_FILES_SCANNED: int = 200
MINIMUM_COVERED_PUBLIC_FUNCTIONS: int = 1
MAX_PAIRED_TEST_COVERAGE_ISSUES: int = 25
MISSING_PAIRED_TEST_GUIDANCE: str = (
    "The paired test suite covers this module and needs a behavioral test for "
    "this function. Add a test that checks its return value or side effect "
    "(CODE_RULES TDD paired-test rule)."
)
TEST_SUITE_OMITS_FUNCTION_GUIDANCE: str = (
    "The paired test suite covers this module and needs a behavioral test for "
    "this public function. Add a test that checks its return value or side effect, "
    "or remove the function (CODE_RULES TDD paired-test rule)."
)
