"""Configuration constants for the send_user_file_open_locally_blocker PreToolUse hook."""

TOOL_NAME: str = "SendUserFile"

PROACTIVE_STATUS: str = "proactive"

CORRECTIVE_MESSAGE: str = (
    "BLOCKED [open-locally]: SendUserFile attaches a file to the session, which "
    "does not let the user see it while they are at the terminal. Open the file on "
    "screen in its own viewer:\n"
    "  Start-Process pwsh -WindowStyle Hidden -ArgumentList "
    "'-NoProfile','-File',\"$HOME\\.claude\\scripts\\Show-Asset.ps1\","
    "'<path 1>','<path 2>'\n"
    "Show-Asset.ps1 sizes each image window to the image and opens every other file "
    "type in its default app. Pass every path the user named.\n"
    "The one allowed attach is a phone push: when the user has stepped away and you "
    'want the file to reach their phone, call SendUserFile with status "proactive".'
)
