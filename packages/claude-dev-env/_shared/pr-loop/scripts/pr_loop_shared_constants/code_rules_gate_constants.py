"""Constants for code_rules_gate.py per CODE_RULES centralized-config rule."""

import re

STAGED_ATTESTATION_SCHEMA_VERSION: int = 1
STAGED_ATTESTATION_FILENAME: str = "code-rules-staged-attestation.json"
STAGED_ATTESTATION_TEMPORARY_PREFIX: str = ".code-rules-staged-attestation-"
STAGED_ATTESTATION_ENCODING: str = "utf-8"
STAGED_ATTESTATION_GIT_TIMEOUT_SECONDS: int = 30
STAGED_ATTESTATION_SCHEMA_VERSION_KEY: str = "schema_version"
STAGED_ATTESTATION_WORKTREE_KEY: str = "worktree"
STAGED_ATTESTATION_HEAD_OID_KEY: str = "head_oid"
STAGED_ATTESTATION_INDEX_TREE_OID_KEY: str = "index_tree_oid"
ALL_GIT_INDEX_TREE_OID_COMMAND: tuple[str, ...] = ("write-tree",)
ALL_GIT_TOP_LEVEL_AND_PRIVATE_DIRECTORY_COMMAND: tuple[str, ...] = (
    "rev-parse",
    "--show-toplevel",
    "--git-dir",
)
ALL_GIT_HEAD_OID_COMMAND: tuple[str, ...] = ("rev-parse", "--verify", "HEAD")
ALL_GIT_SYMBOLIC_HEAD_COMMAND: tuple[str, ...] = (
    "symbolic-ref",
    "--quiet",
    "HEAD",
)
UNBORN_HEAD_OID: str = "UNBORN_HEAD"
EXPECTED_TOP_LEVEL_AND_PRIVATE_DIRECTORY_LINE_COUNT: int = 2
ALL_GIT_TOP_LEVEL_COMMAND: tuple[str, ...] = ("git", "rev-parse", "--show-toplevel")
ALL_GIT_HEAD_COMMAND: tuple[str, ...] = ("git", "rev-parse", "HEAD")
EMPTY_GIT_TREE_OID: str = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
ALL_GIT_EMPTY_TREE_COMMIT_COMMAND: tuple[str, ...] = (
    "git",
    "commit-tree",
    EMPTY_GIT_TREE_OID,
    "-m",
    "code-rules staged-test snapshot",
)
ALL_GIT_WRITE_TREE_COMMAND: tuple[str, ...] = ("git", "write-tree")
ALL_GIT_WORKTREE_ADD_COMMAND: tuple[str, ...] = (
    "git",
    "worktree",
    "add",
    "--detach",
    "--no-checkout",
)
ALL_GIT_READ_TREE_COMMAND: tuple[str, ...] = ("git", "read-tree")
ALL_GIT_CHECKOUT_INDEX_COMMAND: tuple[str, ...] = (
    "git",
    "checkout-index",
    "--all",
    "--force",
    "--ignore-skip-worktree-bits",
)
ALL_GIT_WORKTREE_REMOVE_COMMAND: tuple[str, ...] = (
    "git",
    "worktree",
    "remove",
    "--force",
)
ALL_GIT_WORKTREE_PRUNE_COMMAND: tuple[str, ...] = ("git", "worktree", "prune")

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
ALL_STAGED_PYTEST_ARGUMENTS: tuple[str, ...] = ("-q",)

CODE_RULES_GATE_PYTHON_ENV_VAR: str = "CODE_RULES_GATE_PYTHON"

CODE_RULES_GATE_PYTHONPATH_ENV_VAR: str = "CODE_RULES_GATE_PYTHONPATH"

PYTHONPATH_ENV_VAR: str = "PYTHONPATH"
STAGED_TEST_ORIGINAL_ROOT_ENV_VAR: str = "CODE_RULES_STAGED_TEST_ORIGINAL_ROOT"
STAGED_TEST_SNAPSHOT_ROOT_ENV_VAR: str = "CODE_RULES_STAGED_TEST_SNAPSHOT_ROOT"
STAGED_TEST_PROVENANCE_FAILURE_EXIT_CODE: int = 4
STAGED_TEST_PROVENANCE_FAILURE_MESSAGE: str = (
    "code_rules_gate: staged pytest imported project code from the live worktree: {path}"
)
ALL_EDITABLE_MAPPING_ATTRIBUTE_NAMES: tuple[str, ...] = ("MAPPING", "mapping")

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
