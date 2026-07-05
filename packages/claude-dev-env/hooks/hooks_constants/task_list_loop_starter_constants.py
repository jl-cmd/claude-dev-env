"""Directive text for the task_list_loop_starter SessionStart hook."""

from __future__ import annotations

__all__ = [
    "TASK_LIST_MAINTENANCE_INSTRUCTION",
    "TASK_LIST_LOOP_DIRECTIVE",
]

TASK_LIST_MAINTENANCE_INSTRUCTION = "build or update the task list using the task tools"

TASK_LIST_LOOP_DIRECTIVE = (
    "TASK LIST MAINTENANCE: Keep this session's task list current on a 10-minute "
    "cadence. If a task-list maintenance loop is not already running this session, "
    "start one now with Claude Code's built-in /loop skill on a 10-minute interval: "
    f'/loop 10m "{TASK_LIST_MAINTENANCE_INSTRUCTION}". Run that instruction once '
    "immediately, then let the loop refresh the list every 10 minutes."
)
