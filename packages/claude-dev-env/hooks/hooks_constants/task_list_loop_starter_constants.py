"""Directive text for the task_list_loop_starter SessionStart hook."""

from __future__ import annotations

__all__ = [
    "TASK_LIST_MAINTENANCE_INSTRUCTION",
    "TASK_LIST_LOOP_DIRECTIVE",
]

TASK_LIST_MAINTENANCE_INSTRUCTION = "build or update the task list using the task tools"

TASK_LIST_LOOP_DIRECTIVE = (
    "TASK LIST MAINTENANCE: Keep the task list current on a 10-minute interval. Start "
    "Claude Code's built-in /loop skill with the maintenance instruction: "
    f'/loop 10m "{TASK_LIST_MAINTENANCE_INSTRUCTION}". Run it once immediately, '
    "then let the loop refresh the list every 10 minutes."
)
