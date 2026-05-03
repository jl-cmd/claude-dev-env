"""Configuration constants for the bugteam preflight script."""

BUGTEAM_PREFLIGHT_SKIP_ENV_VAR_NAME: str = "BUGTEAM_PREFLIGHT_SKIP"

BUGTEAM_PREFLIGHT_SKIP_ENABLED_VALUE: str = "1"

GIT_DIRECTORY_NAME: str = ".git"

CLAUDE_DIRECTORY_NAME: str = ".claude"

VENV_DIRECTORY_NAME: str = ".venv"

PYTEST_INI_FILENAME: str = "pytest.ini"

PYPROJECT_TOML_FILENAME: str = "pyproject.toml"

PRE_COMMIT_CONFIG_YAML_FILENAME: str = ".pre-commit-config.yaml"

PYTEST_TOML_TABLE_PREFIX: str = "[tool.pytest"

ALL_TEST_FILE_PATTERNS_FOR_DISCOVERY: tuple[str, str] = (
    "test_*.py",
    "*_test.py",
)

ALL_TESTS_DIRECTORY_IGNORE_PARTS: frozenset[str] = frozenset(
    {"site-packages", VENV_DIRECTORY_NAME, "venv", "node_modules"}
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

PYTEST_NO_TESTS_COLLECTED_EXIT_CODE: int = 5
