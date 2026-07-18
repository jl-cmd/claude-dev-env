"""Named constants for the claude chain weekly-usage report tool.

Per the project's configuration conventions, every scalar and structural
constant the usage reporter needs lives here rather than inline in the module.
"""

from __future__ import annotations

FULL_WEEKLY_PERCENT: float = 100.0
"""Percent scale ceiling for weekly utilization (remaining = this minus used)."""

USAGE_PAUSE_SKILL_DIRECTORY_NAME: str = "skills"
"""Package-root directory name that holds skill trees (sibling of ``scripts/``)."""

USAGE_PAUSE_SKILL_NAME: str = "usage-pause"
"""Skill directory name under ``skills/`` that owns the OAuth usage probe."""

USAGE_PAUSE_SCRIPTS_DIRECTORY_NAME: str = "scripts"
"""Directory under the usage-pause skill that holds the OAuth probe module."""

RESOLVE_USAGE_WINDOW_MODULE_NAME: str = "resolve_usage_window"
"""Module name of the usage-pause OAuth probe loader."""

RESOLVE_USAGE_WINDOW_FILENAME: str = "resolve_usage_window.py"
"""Filename of the usage-pause OAuth probe module on disk."""

JSON_ACCOUNTS_KEY: str = "accounts"
"""Top-level key in the CLI JSON report holding the per-account list."""

JSON_COMMAND_KEY: str = "command"
"""Per-account JSON key naming the chain binary."""

JSON_WEEKLY_REMAINING_PERCENT_KEY: str = "weekly_remaining_percent"
"""Per-account JSON key for remaining weekly usage percent (or null)."""

JSON_ERROR_KEY: str = "error"
"""Per-account JSON key carrying the unmeasurable-reason string."""

CLI_CONFIG_PATH_FLAG: str = "--config-path"
"""CLI flag that overrides the chain configuration file path."""

NO_ACCESS_TOKEN_ERROR_TEMPLATE: str = (
    "no usable bearer token from the OAuth credential file at {credentials_path}"
)
"""Error when the entry credential file yields no usable OAuth bearer."""

WEEKLY_UTILIZATION_MISSING_ERROR: str = (
    "usage response carried no weekly utilization"
)
"""Error when the OAuth usage payload has no readable seven_day utilization."""

USAGE_PROBE_FAILED_ERROR_TEMPLATE: str = "usage probe failed: {error}"
"""Error when the OAuth usage HTTP probe raises."""

RESOLVE_USAGE_WINDOW_MISSING_ERROR_TEMPLATE: str = (
    "usage-pause probe module not found at {module_path}"
)
"""Error when the resolve_usage_window script cannot be located on disk."""
