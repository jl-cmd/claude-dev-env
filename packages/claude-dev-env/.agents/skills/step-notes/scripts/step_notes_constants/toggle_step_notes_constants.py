"""Constants for the step-notes toggle CLI."""

from pathlib import Path

STEP_NOTES_ON_FLAG_PATH = Path.home() / ".claude" / ".step-notes-on"
ON_ACTION = "on"
OFF_ACTION = "off"
STATUS_ACTION = "status"
FLIP_ACTION = "flip"
ALL_ACTIONS = (ON_ACTION, OFF_ACTION, STATUS_ACTION, FLIP_ACTION)
ON_REPORT = "Step notes are on. Each tool call needs a short status line before it."
OFF_REPORT = "Step notes are off. Tool calls run without a status line."
