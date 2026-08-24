"""Environment keys and values used by destructive-command hooks."""

from __future__ import annotations

ALL_KNOWN_TEMPORARY_ENVIRONMENT_VARIABLE_NAMES: frozenset[str] = frozenset(
    {
        "TEMP",
        "TMP",
        "TMPDIR",
        "CLAUDE_JOB_DIR",
    }
)
ALL_TRUTHY_ENV_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})
DESTRUCTIVE_DENY_MODE_ENV_VAR: str = "CLAUDE_DESTRUCTIVE_DENY_MODE"
EPHEMERAL_AUTO_ALLOW_DISABLE_ENV_VAR: str = (
    "CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW"
)
GH_REDIRECT_ACTIVE_ENV_VAR: str = "CLAUDE_GH_REDIRECT_ACTIVE"
