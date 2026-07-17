"""Constants for the issue-tracker commit and push reminder hook.

Holds the git command tokens that mark a commit or push (the git executable
names, the commit and push subcommands, the argument-taking global flags the
token walk skips, the flag prefix, and the flag-plus-value token span), the
shell command-separator tokens that mark a command boundary, the path
separators the token-basename split uses, the tool-input payload keys the hook
reads, the PreToolUse allow-payload keys and values it emits, and the reminder
text it returns as additionalContext.
"""

from __future__ import annotations

__all__ = [
    "ALL_GIT_EXECUTABLE_TOKENS",
    "ALL_REMINDER_TRIGGER_SUBCOMMANDS",
    "ALL_ARGUMENT_TAKING_GLOBAL_FLAGS",
    "ALL_COMMAND_SEPARATOR_TOKENS",
    "FLAG_TOKEN_PREFIX",
    "FLAG_WITH_VALUE_TOKEN_SPAN",
    "WINDOWS_PATH_SEPARATOR",
    "POSIX_PATH_SEPARATOR",
    "TOOL_INPUT_PAYLOAD_KEY",
    "COMMAND_INPUT_KEY",
    "HOOK_SPECIFIC_OUTPUT_KEY",
    "HOOK_EVENT_NAME_KEY",
    "PERMISSION_DECISION_KEY",
    "ADDITIONAL_CONTEXT_KEY",
    "PRE_TOOL_USE_EVENT_NAME",
    "ALLOW_PERMISSION_DECISION",
    "ISSUE_TRACKER_COMMIT_REMINDER_TEXT",
]

_GIT_EXECUTABLE_NAME = "git"
_GIT_EXECUTABLE_WINDOWS_NAME = "git.exe"
ALL_GIT_EXECUTABLE_TOKENS: frozenset[str] = frozenset(
    {_GIT_EXECUTABLE_NAME, _GIT_EXECUTABLE_WINDOWS_NAME}
)

_GIT_COMMIT_SUBCOMMAND = "commit"
_GIT_PUSH_SUBCOMMAND = "push"
ALL_REMINDER_TRIGGER_SUBCOMMANDS: frozenset[str] = frozenset(
    {_GIT_COMMIT_SUBCOMMAND, _GIT_PUSH_SUBCOMMAND}
)

ALL_ARGUMENT_TAKING_GLOBAL_FLAGS: frozenset[str] = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
)
FLAG_TOKEN_PREFIX = "-"
FLAG_WITH_VALUE_TOKEN_SPAN = 2

ALL_COMMAND_SEPARATOR_TOKENS: frozenset[str] = frozenset({"&&", "||", "|", ";", "&"})

WINDOWS_PATH_SEPARATOR = "\\"
POSIX_PATH_SEPARATOR = "/"

TOOL_INPUT_PAYLOAD_KEY = "tool_input"
COMMAND_INPUT_KEY = "command"

HOOK_SPECIFIC_OUTPUT_KEY = "hookSpecificOutput"
HOOK_EVENT_NAME_KEY = "hookEventName"
PERMISSION_DECISION_KEY = "permissionDecision"
ADDITIONAL_CONTEXT_KEY = "additionalContext"
PRE_TOOL_USE_EVENT_NAME = "PreToolUse"
ALLOW_PERMISSION_DECISION = "allow"

ISSUE_TRACKER_COMMIT_REMINDER_TEXT = (
    "ISSUE TRACKER: This commit or push advances tracked work. Update the tracker "
    "now — refresh each affected issue's status section in place, check off every "
    "finished child in its epic checklist, and give a finished sub-issue's commit "
    "or pull request a 'Closes #N' line so the issue closes when it merges."
)
