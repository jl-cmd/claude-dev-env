"""Configuration constants for the bugteam preflight check script."""

from __future__ import annotations

BUGTEAM_PREFLIGHT_SKIP_ENV_VAR_NAME: str = "BUGTEAM_PREFLIGHT_SKIP"
EXPECTED_HOOKS_PATH_SUFFIX: str = "hooks/git-hooks"
ENFORCEMENT_ABSENT_MESSAGE: str = (
    "Git-side CODE_RULES enforcement is not active on this host.\n"
    "Run: npx claude-dev-env .\n"
    "Or set core.hooksPath at any scope, e.g.:\n"
    "  git config --global core.hooksPath ~/.claude/hooks/git-hooks"
)
PYTEST_EXIT_CODE_NO_TESTS_COLLECTED: int = 5
EXIT_CODE_HOOKS_PATH_CHECK_FAILED: int = 1
ALL_DISCOVERY_IGNORE_DIRECTORIES: frozenset[str] = frozenset(
    {"site-packages", ".venv", "venv", "node_modules"}
)
BUGTEAM_PREFLIGHT_PREFIX: str = "bugteam_preflight: "


ALL_GIT_CONFIG_HOOKS_PATH_ARGUMENTS: tuple[str, ...] = (
    "config",
    "--get",
    "core.hooksPath",
)
ALL_PRE_COMMIT_ARGUMENTS: tuple[str, ...] = (
    "pre-commit",
    "run",
    "--all-files",
)
GIT_DIRECTORY_NAME: str = ".git"
PYTEST_INI_FILENAME: str = "pytest.ini"
PYPROJECT_FILENAME: str = "pyproject.toml"
PYPROJECT_PYTEST_SECTION_PREFIX: str = "[tool.pytest"
PRE_COMMIT_CONFIG_FILENAME: str = ".pre-commit-config.yaml"
