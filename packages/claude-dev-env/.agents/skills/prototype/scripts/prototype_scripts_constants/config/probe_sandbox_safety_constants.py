"""Constants for the sandbox safety-hook probe.

Groups: the PreToolUse envelope keys and their probe payloads, the tool-input
keys, the hook decision keys and the block decisions, the join separators, the
destructive and personal-data probe payloads, the probe hook timeout, and the
exit codes.
"""

from __future__ import annotations

ENVELOPE_SESSION_ID_KEY = "session_id"
ENVELOPE_PROBE_SESSION_ID = "probe"
ENVELOPE_HOOK_EVENT_NAME_KEY = "hook_event_name"
ENVELOPE_PRE_TOOL_USE_EVENT_NAME = "PreToolUse"
ENVELOPE_TOOL_NAME_KEY = "tool_name"
ENVELOPE_TOOL_INPUT_KEY = "tool_input"

TOOL_INPUT_COMMAND_KEY = "command"
TOOL_INPUT_FILE_PATH_KEY = "file_path"
TOOL_INPUT_CONTENT_KEY = "content"

HOOK_SPECIFIC_REPLY_KEY = "hookSpecificOutput"
PERMISSION_DECISION_KEY = "permissionDecision"
HARD_DENY_DECISION = "deny"

MATCHER_JOIN_SEPARATOR = ", "
COMMAND_TOKEN_JOIN_SEPARATOR = " "

DESTRUCTIVE_PROBE_TOOL_NAME = "Bash"
ALL_DESTRUCTIVE_PROBE_COMMAND_TOKENS = ("rm", "-rf", "/var/log/myapp")
DESTRUCTIVE_PROBE_COMMAND = COMMAND_TOKEN_JOIN_SEPARATOR.join(
    ALL_DESTRUCTIVE_PROBE_COMMAND_TOKENS
)

PII_PROBE_TOOL_NAME = "Write"
PII_PROBE_FILE_PATH = "src/config.env.example.md"
PII_PROBE_TOKEN_PREFIX = "ghp" + "_"
PII_PROBE_TOKEN_BODY_CHARACTER = "C"
PII_PROBE_TOKEN_BODY_LENGTH = 36
PII_PROBE_CONTENT_TEMPLATE = "TOKEN={secret}\n"

PROBE_HOOK_TIMEOUT_SECONDS = 30

PROBE_SUCCESS_EXIT_CODE = 0
PROBE_FAILURE_EXIT_CODE = 3
