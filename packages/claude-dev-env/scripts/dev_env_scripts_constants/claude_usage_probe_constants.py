"""Named constants for the Claude session usage probe wrapper.

``claude_usage_probe.py`` composes the usage-pause resolver
(``resolve_usage_window.py``) and emits a small skill-facing JSON report.
Every scalar and structural constant the probe needs lives here.
"""

from __future__ import annotations

SESSION_UTILIZATION_NO_USAGE_THRESHOLD: float = 100.0
"""Session utilization at or above this percent means no 5-hour usage left."""

USAGE_PROBE_SUBPROCESS_TIMEOUT_SECONDS: int = 20
"""Timeout for one ``resolve_usage_window.py`` subprocess invocation, in seconds."""

SKILLS_DIRECTORY_NAME: str = "skills"
"""Directory under the package root and under ``~/.claude`` that holds skills."""

USAGE_PAUSE_SKILL_DIRECTORY_NAME: str = "usage-pause"
"""Skill folder that owns the OAuth usage-window resolver."""

USAGE_PAUSE_SCRIPTS_DIRECTORY_NAME: str = "scripts"
"""Scripts subdirectory under the usage-pause skill."""

RESOLVE_USAGE_WINDOW_SCRIPT_NAME: str = "resolve_usage_window.py"
"""Basename of resolve_usage_window.py under the usage-pause scripts directory."""

RESULT_KEY_SESSION_UTILIZATION: str = "session_utilization"
"""JSON report key for 5-hour session utilization percent, or null."""

RESULT_KEY_WEEKLY_UTILIZATION: str = "weekly_utilization"
"""JSON report key for weekly utilization percent, or null."""

RESULT_KEY_WEEKLY_NEAR_CAP: str = "weekly_near_cap"
"""JSON report key for the weekly near-cap warn flag, or null when unknown."""

RESULT_KEY_SESSION_HAS_USAGE_LEFT: str = "session_has_usage_left"
"""JSON report key: true when session meter is known and below threshold."""

RESULT_KEY_SOURCE: str = "source"
"""JSON report key naming the resolver source label or unavailable."""

RESULT_KEY_PROBE_OK: str = "probe_ok"
"""JSON report key that is true only when the usage-pause resolver succeeded."""

SOURCE_UNAVAILABLE: str = "unavailable"
"""Source label when the usage-pause resolver cannot run or returns non-zero."""

EXIT_CODE_PROBE_REPORT: int = 0
"""CLI exit when a JSON report was written (including probe_ok false)."""
