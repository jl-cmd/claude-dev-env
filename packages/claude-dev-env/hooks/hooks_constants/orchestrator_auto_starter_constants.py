"""Constants for the orchestrator SessionStart injector hook.

Holds the environment toggle name that gates the injector and the directive text
it injects to ask Claude to run the ``/orchestrator`` skill.
"""

from __future__ import annotations

__all__ = [
    "AUTO_ORCHESTRATOR_ENV_VAR_NAME",
    "ORCHESTRATOR_START_DIRECTIVE",
]

AUTO_ORCHESTRATOR_ENV_VAR_NAME = "CLAUDE_AUTO_ORCHESTRATOR"

ORCHESTRATOR_START_DIRECTIVE = (
    "ORCHESTRATOR MODE: Run Claude Code's /orchestrator skill now to plan this "
    "session and delegate execution to workflow-backed agents while a shared "
    "advisor reviews the hard decisions."
)
