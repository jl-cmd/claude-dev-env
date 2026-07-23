"""Constants for code_rules_gate.py per CODE_RULES centralized-config rule."""

import re

MAX_VIOLATIONS_PER_CHECK: int = 3

GATE_ERROR_EXIT_CODE: int = 2

EMPTY_FILE_SET_EXIT_CODE: int = 3

EMPTY_FILE_SET_MESSAGE: str = (
    "code_rules_gate: the resolved file set is empty; nothing was inspected."
)

INSPECTED_COUNT_MESSAGE: str = "code_rules_gate: inspected {inspected_count} file(s)."

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

ALL_CODE_FILE_EXTENSIONS: frozenset[str] = frozenset({".py", ".js", ".ts", ".tsx", ".jsx"})

TESTS_PATH_SEGMENT: str = "/tests/"

ALL_TEST_FILENAME_SUFFIXES: tuple[str, ...] = ("_test.py",)

ALL_TEST_FILENAME_GLOB_SUFFIXES: tuple[str, ...] = (
    ".test.",
    ".spec.",
)

TEST_CONFTEST_FILENAME: str = "conftest.py"

TEST_FILENAME_PREFIX: str = "test_"

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

ALL_GIT_LS_FILES_UNTRACKED_NULL_TERMINATED_COMMAND: tuple[str, ...] = (
    "git",
    "ls-files",
    "--others",
    "--exclude-standard",
    "-z",
)


ALL_PYTEST_MODULE_INVOCATION: tuple[str, ...] = (
    "-m",
    "pytest",
    "-q",
)

CODE_RULES_GATE_PYTHON_ENV_VAR: str = "CODE_RULES_GATE_PYTHON"

CODE_RULES_GATE_PYTHONPATH_ENV_VAR: str = "CODE_RULES_GATE_PYTHONPATH"

PYTHONPATH_ENV_VAR: str = "PYTHONPATH"

ALL_VENV_DIRECTORY_NAMES: tuple[str, ...] = (".venv", "venv")

ALL_WINDOWS_VENV_PYTHON_RELATIVE_PATH_SEGMENTS: tuple[str, ...] = (
    "Scripts",
    "python.exe",
)

ALL_POSIX_VENV_PYTHON_RELATIVE_PATH_SEGMENTS: tuple[str, ...] = ("bin", "python")

STAGED_PYTEST_TIMEOUT_SECONDS: int = 600

MAXIMUM_STAGED_PYTEST_COMMAND_LINE_CHARACTERS: int = 24000

COMMAND_LINE_ARGUMENT_SEPARATOR_LENGTH: int = 1

STAGED_TEST_FAILURE_HEADER: str = (
    "code_rules_gate: staged test file(s) failed under pytest; commit blocked."
)

PYTEST_INI_FILENAME: str = "pytest.ini"

PYPROJECT_TOML_FILENAME: str = "pyproject.toml"

SETUP_CFG_FILENAME: str = "setup.cfg"

TOX_INI_FILENAME: str = "tox.ini"

PYPROJECT_PYTEST_CONFIG_SECTION: str = "[tool.pytest.ini_options]"

SETUP_CFG_PYTEST_CONFIG_SECTION: str = "[tool:pytest]"

TOX_INI_PYTEST_CONFIG_SECTION: str = "[pytest]"

ALL_PYTEST_CONFIG_FILE_SECTIONS: tuple[tuple[str, str | None], ...] = (
    (PYTEST_INI_FILENAME, None),
    (PYPROJECT_TOML_FILENAME, PYPROJECT_PYTEST_CONFIG_SECTION),
    (SETUP_CFG_FILENAME, SETUP_CFG_PYTEST_CONFIG_SECTION),
    (TOX_INI_FILENAME, TOX_INI_PYTEST_CONFIG_SECTION),
)

STAGED_TEST_GROUP_FAILURE_MESSAGE: str = (
    "code_rules_gate: staged test group rooted at {group_root} failed under pytest; commit blocked."
)

MINIMUM_STAGED_PYTEST_PYTHON_MAJOR: int = 3

MINIMUM_STAGED_PYTEST_PYTHON_MINOR: int = 12

JUNIT_XML_FLAG_PREFIX: str = "--junitxml="

JUNIT_XML_TESTCASE_TAG: str = "testcase"

JUNIT_XML_FAILURE_TAG: str = "failure"

JUNIT_XML_ERROR_TAG: str = "error"

JUNIT_XML_CLASSNAME_ATTRIBUTE: str = "classname"

JUNIT_XML_NAME_ATTRIBUTE: str = "name"

JUNIT_XML_MISSING_ATTRIBUTE_FALLBACK: str = ""

REGRESSION_JUNIT_TEMP_DIRECTORY_PREFIX: str = "code_rules_gate_junit_"

REGRESSION_STAGED_JUNIT_SUBDIRECTORY_NAME: str = "staged"

REGRESSION_BASELINE_JUNIT_SUBDIRECTORY_NAME: str = "baseline"

REGRESSION_GIT_STASH_MESSAGE: str = "code_rules_gate: regression-baseline snapshot"

ALL_GIT_HEAD_EXISTS_ARGS: tuple[str, ...] = ("rev-parse", "--verify", "HEAD")

ALL_GIT_STASH_PUSH_ARGS: tuple[str, ...] = (
    "stash",
    "push",
    "--quiet",
    "--message",
    REGRESSION_GIT_STASH_MESSAGE,
)

ALL_GIT_STASH_POP_ARGS: tuple[str, ...] = ("stash", "pop", "--quiet", "--index")

REGRESSION_NO_BASELINE_MESSAGE: str = (
    "code_rules_gate: no prior commit to compare against (first commit on this branch); "
    "every staged test failure blocks."
)

REGRESSION_STASH_FAILED_MESSAGE: str = (
    "code_rules_gate: could not snapshot the pre-staged baseline (git stash push failed); "
    "falling back to blocking on every staged test failure."
)

REGRESSION_STASH_POP_FAILED_MESSAGE: str = (
    "code_rules_gate: git stash pop failed after the baseline check — your staged changes "
    "are sitting in the stash, not lost. Run 'git stash list' then 'git stash pop' to "
    "restore them by hand."
)

REGRESSION_PRE_EXISTING_FAILURE_BYPASSED_MESSAGE: str = (
    "code_rules_gate: staged test group rooted at {group_root} has {count} failure(s) "
    "already present before this change (not caused by it); not blocking."
)

REGRESSION_GROUP_FAILURE_MESSAGE: str = (
    "code_rules_gate: staged test group rooted at {group_root} has {count} failure(s) "
    "this change introduces; commit blocked."
)
