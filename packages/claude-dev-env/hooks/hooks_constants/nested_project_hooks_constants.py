"""Configuration constants for the ``nested_project_hooks`` forwarder."""

from __future__ import annotations

PROJECT_DIRECTORY_ENVIRONMENT_VARIABLE: str = "CLAUDE_PROJECT_DIR"
CHECKOUT_MARKER_NAME: str = ".git"
SETTINGS_DIRECTORY_NAME: str = ".claude"
SETTINGS_FILE_NAME: str = "settings.json"
SETTINGS_ENCODING: str = "utf-8"

HOOKS_KEY: str = "hooks"
MATCHER_KEY: str = "matcher"
HOOK_TYPE_KEY: str = "type"
COMMAND_HOOK_TYPE: str = "command"
COMMAND_KEY: str = "command"
TIMEOUT_KEY: str = "timeout"
DEFAULT_HOOK_TIMEOUT_SECONDS: float = 600.0
ALL_MATCH_EVERYTHING_MATCHERS: frozenset[str] = frozenset({"", "*"})

HOOK_EVENT_NAME_KEY: str = "hook_event_name"
PRE_TOOL_USE_EVENT: str = "PreToolUse"
SESSION_START_EVENT: str = "SessionStart"
ALL_MATCH_TARGET_KEYS_BY_EVENT: dict[str, str] = {
    PRE_TOOL_USE_EVENT: "tool_name",
    SESSION_START_EVENT: "source",
}

ALL_SHELL_PROGRAM_NAMES: tuple[str, ...] = ("bash", "sh")
SHELL_COMMAND_FLAG: str = "-c"

BLOCKING_EXIT_CODE: int = 2
HOOK_SPECIFIC_OUTPUT_KEY: str = "hookSpecificOutput"
HOOK_EVENT_NAME_OUTPUT_KEY: str = "hookEventName"
PERMISSION_DECISION_KEY: str = "permissionDecision"
ALL_FORWARDED_PERMISSION_DECISIONS: frozenset[str] = frozenset({"deny", "ask"})
ADDITIONAL_CONTEXT_KEY: str = "additionalContext"
CONTEXT_SECTION_SEPARATOR: str = "\n\n"
