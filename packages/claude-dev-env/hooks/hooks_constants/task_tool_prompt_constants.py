"""Directive text for the task_tool_prompt SessionStart hook."""

from __future__ import annotations

__all__ = [
    "TASK_TOOL_DIRECTIVE",
]

TASK_TOOL_DIRECTIVE = (
    "TASK TRACKING: Track this session's work with the session's task or todo "
    "tracking tool, whichever this host provides. Create tasks at the start "
    "of the session, then update them as work proceeds."
)
