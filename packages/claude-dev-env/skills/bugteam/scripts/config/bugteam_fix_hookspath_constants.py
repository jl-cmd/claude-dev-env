"""Configuration constants for bugteam_fix_hookspath auto-remediation script."""

from __future__ import annotations

HOOKS_PATH_SUFFIX: str = "hooks/git-hooks"

ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS: tuple[str, str, str] = (
    ".claude",
    "hooks",
    "git-hooks",
)

ALL_HOME_ENV_VAR_NAMES: tuple[str, str] = ("HOME", "USERPROFILE")

PREFLIGHT_NO_PYTEST_FLAG: str = "--no-pytest"

PREFLIGHT_REPO_ROOT_FLAG: str = "--repo-root"
