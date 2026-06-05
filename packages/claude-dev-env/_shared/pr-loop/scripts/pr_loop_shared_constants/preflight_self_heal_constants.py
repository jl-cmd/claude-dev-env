"""Configuration constants for the preflight self-heal helper.

The helper unsets any local-scope ``core.hooksPath`` entry git seeds into a
new worktree's config so the canonical global setting takes effect without
preflight surfacing a failure or invoking the auto-remediation script.
"""

from __future__ import annotations

ALL_GIT_CONFIG_LOCAL_GET_ALL_HOOKS_PATH_ARGUMENTS: tuple[str, ...] = (
    "config",
    "--local",
    "--get-all",
    "core.hooksPath",
)
ALL_GIT_CONFIG_LOCAL_UNSET_ALL_HOOKS_PATH_ARGUMENTS: tuple[str, ...] = (
    "config",
    "--local",
    "--unset-all",
    "core.hooksPath",
)
ALL_GIT_CONFIG_GLOBAL_GET_ALL_HOOKS_PATH_COMMAND: tuple[str, ...] = (
    "git",
    "config",
    "--global",
    "--get-all",
    "core.hooksPath",
)
