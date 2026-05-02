"""Configuration constants for fix_hookspath auto-remediation script."""

ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS: tuple[str, str, str] = (
    ".claude",
    "hooks",
    "git-hooks",
)

HOOKS_PATH_SUFFIX: str = "/".join(ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS)

HOOKS_PATH_VERIFICATION_SUFFIX: str = "/".join(ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS[-2:])

ALL_HOME_ENV_VAR_NAMES: tuple[str, str] = ("HOME", "USERPROFILE")

PREFLIGHT_NO_PYTEST_FLAG: str = "--no-pytest"

PREFLIGHT_REPO_ROOT_FLAG: str = "--repo-root"

ALL_GIT_GLOBAL_GET_CORE_HOOKS_PATH_COMMAND: tuple[str, ...] = (
    "git",
    "config",
    "--global",
    "--get",
    "core.hooksPath",
)
