"""Constants for the step-note gate PreToolUse hook."""

from pathlib import Path

STEP_NOTES_ON_FLAG_PATH = Path.home() / ".claude" / ".step-notes-on"
POLL_INTERVAL_SECONDS = 0.05
POLL_LIMIT_SECONDS = 8.0
TAIL_WINDOW_BYTES = 1_000_000
BLOCK_EXIT_CODE = 2
ALLOW_EXIT_CODE = 0
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
TEXT_BLOCK_TYPE = "text"
TOOL_USE_BLOCK_TYPE = "tool_use"
BLOCK_MESSAGE = (
    "Status line missing. Start the message with a short status line that names "
    "this action, such as 'Reading hooks.json.', then retry the call. "
    "The user turns this gate on and off with /step-notes."
)
