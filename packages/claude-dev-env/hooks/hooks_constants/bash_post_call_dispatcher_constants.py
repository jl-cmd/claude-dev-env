"""Constants for the Bash PostToolUse dispatcher.

Holds the ordered hosted-hook roster this dispatcher runs after a Bash call
finishes. Reuses ``BashHostedHookEntry`` and the Bash-only tool-name set from
``bash_pre_tool_use_dispatcher_constants`` -- the entry shape and the tool-name
membership question are identical on the PostToolUse side, so this module adds
no second copy of either.

Also the one home for the harness PostToolUse output contract every hook on
this roster shares: the exit-code prefix a failed call's response text opens
with, and the three payload keys that carry a context note back to the agent.
"""

from __future__ import annotations

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
    ALL_BASH_AND_POWERSHELL_TOOL_NAMES,
    ALL_BASH_ONLY_TOOL_NAMES,
    BashHostedHookEntry,
)

__all__ = [
    "ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES",
    "EXIT_CODE_ERROR_PREFIX",
    "POST_TOOL_USE_HOOK_EVENT_NAME",
    "HOOK_SPECIFIC_OUTPUT_KEY",
    "HOOK_EVENT_NAME_KEY",
    "ADDITIONAL_CONTEXT_KEY",
    "ADDITIONAL_CONTEXT_JOIN_SEPARATOR",
]

ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES: tuple[BashHostedHookEntry, ...] = (
    BashHostedHookEntry("observability/test_failure_recorder.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("advisory/pr_done_reminder.py", ALL_BASH_AND_POWERSHELL_TOOL_NAMES),
    BashHostedHookEntry("advisory/msys_path_conversion_advisor.py", ALL_BASH_ONLY_TOOL_NAMES),
)

EXIT_CODE_ERROR_PREFIX: str = "Error: Exit code "
POST_TOOL_USE_HOOK_EVENT_NAME: str = "PostToolUse"
HOOK_SPECIFIC_OUTPUT_KEY: str = "hookSpecificOutput"
HOOK_EVENT_NAME_KEY: str = "hookEventName"
ADDITIONAL_CONTEXT_KEY: str = "additionalContext"
ADDITIONAL_CONTEXT_JOIN_SEPARATOR: str = "\n\n"
