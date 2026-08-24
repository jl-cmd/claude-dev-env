"""Constants for the sandbox safety-settings builder.

Groups: the two safety hook script basenames the sandbox keeps, the matchers
each safety hook must cover, the mapping from basename to those matchers, the
settings JSON key names, the env-block key with the deny-mode env variable and
value, the default live settings source, the pretty-print indent, the join
separator for the missing-basename message, and the exit codes.
"""

from __future__ import annotations

ALL_SAFETY_HOOK_SCRIPT_BASENAMES = (
    "pii_prevention_blocker.py",
    "destructive_command_blocker.py",
)

ALL_PII_REQUIRED_MATCHERS = ("Write", "Edit", "MultiEdit", "Bash")
ALL_DESTRUCTIVE_REQUIRED_MATCHERS = ("Bash",)

ALL_REQUIRED_MATCHERS_BY_SAFETY_BASENAME = {
    ALL_SAFETY_HOOK_SCRIPT_BASENAMES[0]: ALL_PII_REQUIRED_MATCHERS,
    ALL_SAFETY_HOOK_SCRIPT_BASENAMES[1]: ALL_DESTRUCTIVE_REQUIRED_MATCHERS,
}

HOOKS_KEY = "hooks"
PRE_TOOL_USE_KEY = "PreToolUse"
MATCHER_KEY = "matcher"
COMMAND_KEY = "command"
ENV_KEY = "env"

DESTRUCTIVE_DENY_MODE_ENV_VAR = "CLAUDE_DESTRUCTIVE_DENY_MODE"
DESTRUCTIVE_DENY_MODE_ENV_VALUE = "1"

DEFAULT_SETTINGS_SOURCE = "~/.claude/settings.json"
JSON_INDENT_SPACES = 2

MISSING_BASENAMES_JOIN_SEPARATOR = ", "

BUILD_SUCCESS_EXIT_CODE = 0
SETTINGS_MISSING_SAFETY_HOOK_EXIT_CODE = 2
SETTINGS_SOURCE_UNREADABLE_EXIT_CODE = 2
