"""Constants for the hookless sandbox launcher.

Groups: the headless claude executable name and its flag tokens, the default
session timeout, the JSON summary key names, and the missing-path exit code.
"""

from __future__ import annotations

CLAUDE_EXECUTABLE_NAME = "claude"
PROMPT_FLAG = "-p"
BARE_FLAG = "--bare"
SKIP_PERMISSIONS_FLAG = "--dangerously-skip-permissions"
SETTINGS_FLAG = "--settings"

DEFAULT_TIMEOUT_SECONDS = 3600

SUMMARY_KEY_WORKTREE = "worktree"
SUMMARY_KEY_SETTINGS = "settings"
SUMMARY_KEY_EXIT_CODE = "exit_code"

LAUNCH_MISSING_PATH_EXIT_CODE = 2
