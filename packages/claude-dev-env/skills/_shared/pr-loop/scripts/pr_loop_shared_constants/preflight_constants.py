"""Configuration constants for the bugteam preflight script."""

BUGTEAM_PREFLIGHT_SKIP_ENV_VAR_NAME: str = "BUGTEAM_PREFLIGHT_SKIP"

BUGTEAM_PREFLIGHT_SKIP_ENABLED_VALUE: str = "1"

GIT_DIRECTORY_NAME: str = ".git"

CLAUDE_DIRECTORY_NAME: str = ".claude"

PYTEST_INI_FILENAME: str = "pytest.ini"

PYPROJECT_TOML_FILENAME: str = "pyproject.toml"

PRE_COMMIT_CONFIG_YAML_FILENAME: str = ".pre-commit-config.yaml"

PYTEST_TOML_TABLE_PREFIX: str = "[tool.pytest"

PYTEST_FAILED_FIRST_FLAG: str = "--ff"

ALL_GIT_LS_FILES_TEST_DISCOVERY_SUBCOMMAND: tuple[str, ...] = (
    "ls-files",
    "--cached",
    "--others",
    "--exclude-standard",
    "--",
    "**/test_*.py",
    "**/*_test.py",
)

ALL_REPOSITORY_ROOT_MARKER_FILENAMES: tuple[str, str] = (
    GIT_DIRECTORY_NAME,
    PYTEST_INI_FILENAME,
)

ALL_GIT_CONFIG_GET_CORE_HOOKS_PATH_SUBCOMMAND: tuple[str, str, str] = (
    "config",
    "--get",
    "core.hooksPath",
)

ALL_PRE_COMMIT_RUN_ALL_FILES_COMMAND: tuple[str, str, str] = (
    "pre-commit",
    "run",
    "--all-files",
)

ALL_GIT_DIFF_NAME_ONLY_SUBCOMMAND: tuple[str, str] = (
    "diff",
    "--name-only",
)

PYTEST_SCOPE_ALL: str = "all"

PYTEST_SCOPE_CHANGED: str = "changed"

ALL_PYTEST_SCOPE_CHOICES: tuple[str, str] = (PYTEST_SCOPE_ALL, PYTEST_SCOPE_CHANGED)


PYTHON_FILE_SUFFIX: str = ".py"

PYTEST_TEST_FILENAME_PREFIX: str = "test_"

PYTEST_TEST_FILENAME_SUFFIX: str = "_test"

PYTEST_NO_TESTS_COLLECTED_EXIT_CODE: int = 5

TESTS_DIRECTORY_NAME: str = "tests"
