"""Constants for the Codex weekly-usage probe CLI.

Groups: gate threshold, probe report JSON keys, app-server JSON-RPC surface,
rate-limit snapshot field keys, weekly-window sizing, parse patterns for
text status output, source labels, and exit codes.
"""

from __future__ import annotations

WEEKLY_USAGE_GATE_THRESHOLD_PERCENT = 10

USAGE_REPORT_KEY_PERCENT_LEFT = "percent_left"
USAGE_REPORT_KEY_WINDOW_RESET = "window_reset"
USAGE_REPORT_KEY_SOURCE = "source"

CODEX_BINARY_NAME = "codex"
ALL_APP_SERVER_COMMAND_PARTS = ("app-server", "--listen", "stdio://")
APP_SERVER_TIMEOUT_SECONDS = 30
WINDOWS_OS_NAME = "nt"
WINDOWS_COMMAND_SHELL = "cmd"
WINDOWS_COMMAND_SHELL_RUN_FLAG = "/c"
ALL_WINDOWS_SCRIPT_SUFFIXES = (".cmd", ".bat")

JSONRPC_VERSION = "2.0"
JSONRPC_KEY_ID = "id"
JSONRPC_KEY_METHOD = "method"
JSONRPC_KEY_PARAMS = "params"
JSONRPC_KEY_REPLY_BODY = "result"
JSONRPC_KEY_ERROR = "error"
JSONRPC_KEY_VERSION = "jsonrpc"

INITIALIZE_REQUEST_ID = 1
RATE_LIMITS_REQUEST_ID = 2
METHOD_INITIALIZE = "initialize"
METHOD_INITIALIZED = "initialized"
METHOD_RATE_LIMITS_READ = "account/rateLimits/read"

CLIENT_INFO_KEY = "clientInfo"
CLIENT_INFO_NAME_KEY = "name"
CLIENT_INFO_VERSION_KEY = "version"
CLIENT_INFO_NAME = "codex-usage-probe"
CLIENT_INFO_VERSION = "1.0.0"
CAPABILITIES_KEY = "capabilities"
EXPERIMENTAL_API_KEY = "experimentalApi"

RATE_LIMITS_KEY = "rateLimits"
PRIMARY_WINDOW_KEY = "primary"
SECONDARY_WINDOW_KEY = "secondary"
USED_PERCENT_KEY = "usedPercent"
RESETS_AT_KEY = "resetsAt"
WINDOW_DURATION_MINS_KEY = "windowDurationMins"

WEEKLY_WINDOW_DURATION_MINUTES = 10080
PERCENT_FULL = 100
PERCENT_EMPTY = 0

SOURCE_APP_SERVER_RATE_LIMITS = "codex app-server account/rateLimits/read"
SOURCE_TEXT_STATUS = "text-status"
SOURCE_NO_USAGE_SURFACE = "no-usage-surface"

TEXT_WEEKLY_PERCENT_LEFT_PATTERN = (
    r"(?i)weekly(?:\s+(?:limit|usage|cap))?"
    r"[^\n%]{0,40}?"
    r"(?P<percent>\d{1,3}(?:\.\d+)?)\s*%\s*(?:left|remaining)"
)
TEXT_WEEKLY_USED_PERCENT_PATTERN = (
    r"(?i)weekly(?:\s+(?:limit|usage|cap))?"
    r"[^\n%]{0,40}?"
    r"(?P<percent>\d{1,3}(?:\.\d+)?)\s*%\s*(?:used|consumed)"
)
TEXT_WINDOW_RESET_PATTERN = (
    r"(?i)(?:weekly\s+)?(?:resets?|reset\s+at|window\s+reset)"
    r"[:\s]+(?P<reset>[^\s)\].,;]+)"
)

EXIT_CODE_SUCCESS = 0
EXIT_CODE_CRASH = 1

UTF8_ENCODING = "utf-8"
NEWLINE = "\n"
