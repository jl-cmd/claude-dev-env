"""Constants for the opt-in orchestrator SessionStart auto-starter.

Default off. Set CLAUDE_ORCHESTRATOR_AUTO_STARTER_ENABLED to 1/true/yes/on to
emit an additionalContext directive that points the session at the orchestrator
skill. Manual /orchestrator invocation is unchanged.
"""

from __future__ import annotations

ORCHESTRATOR_AUTO_STARTER_ENABLED_ENV_VAR: str = (
    "CLAUDE_ORCHESTRATOR_AUTO_STARTER_ENABLED"
)
ALL_ORCHESTRATOR_STARTER_ENABLED_ENV_VALUES: frozenset[str] = frozenset(
    {"1", "true", "yes", "on"}
)
ORCHESTRATOR_STARTER_TIMEOUT_MILLISECONDS: int = 50

ORCHESTRATOR_SESSION_START_DIRECTIVE: str = (
    "SessionStart orchestrator opt-in is active. Load the orchestrator skill "
    "and run in executor-advisor mode for this session's multi-step work. "
    "Do not invent a second orchestrator path; follow the skill. Manual "
    "/orchestrator remains available unchanged."
)
