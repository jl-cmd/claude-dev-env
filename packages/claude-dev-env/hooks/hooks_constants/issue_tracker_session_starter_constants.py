"""Constants for the repository-gated issue-tracker SessionStart starter.

Default off. Set CLAUDE_ISSUE_TRACKER_SESSION_STARTER_ENABLED to 1/true/yes/on.
Even when enabled, injects only when the session cwd's git root is registered
in ~/.claude/project-paths.json. Missing registry fails closed (no inject).
"""

from __future__ import annotations

ISSUE_TRACKER_SESSION_STARTER_ENABLED_ENV_VAR: str = (
    "CLAUDE_ISSUE_TRACKER_SESSION_STARTER_ENABLED"
)
ALL_ISSUE_TRACKER_STARTER_ENABLED_ENV_VALUES: frozenset[str] = frozenset(
    {"1", "true", "yes", "on"}
)
ISSUE_TRACKER_STARTER_TIMEOUT_MILLISECONDS: int = 50

ISSUE_TRACKER_SESSION_START_DIRECTIVE: str = (
    "SessionStart issue-tracker opt-in is active for this registered repository. "
    "Load the issue-tracker skill when the session needs one GitHub issue action "
    "(open epic, file sub-issue, update status, refresh checklist, close sub-issue). "
    "Manual issue-tracker agent spawn remains available unchanged."
)
