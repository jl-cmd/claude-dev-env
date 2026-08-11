"""Configuration constants for the send_user_file_open_locally_blocker PreToolUse hook."""

TOOL_NAME: str = "SendUserFile"

PROACTIVE_STATUS: str = "proactive"

CORRECTIVE_MESSAGE: str = (
    "BLOCKED [open-locally]: Open each named file with its native Windows app so "
    "terminal users can view it. Use SendUserFile with status \"proactive\" for a "
    "phone push when the user is away."
)
