"""Constants for the MCP session registry and SessionEnd child teardown hook."""

from __future__ import annotations

import os
import re

SESSION_ID_PAYLOAD_KEY: str = "session_id"
HOOK_EVENT_NAME_PAYLOAD_KEY: str = "hook_event_name"
SESSION_START_SOURCE_PAYLOAD_KEY: str = "source"

HOOK_EVENT_SESSION_START: str = "SessionStart"
HOOK_EVENT_SESSION_END: str = "SessionEnd"

SESSION_START_SOURCE_FRESH_STARTUP: str = "startup"

SESSION_ID_UNSAFE_CHARACTERS_PATTERN = re.compile(r"[^A-Za-z0-9_-]")
STATE_FILE_DEFAULT_SESSION_ID: str = "unknown-session"

MCP_SESSION_REGISTRY_DIRECTORY = os.path.join(
    os.path.expanduser("~"),
    ".claude",
    "cache",
    "mcp-session-registry",
)
MCP_SESSION_REGISTRY_FILE_PREFIX: str = "mcp-host-"
MCP_SESSION_REGISTRY_FILE_SUFFIX: str = ".json"

REGISTRY_HOST_PID_KEY: str = "host_pid"
REGISTRY_SESSION_ID_KEY: str = "session_id"
REGISTRY_RECORDED_AT_UNIX_KEY: str = "recorded_at_unix"

ALL_MCP_COMMAND_LINE_MARKERS: tuple[str, ...] = (
    "mcpvault",
    "@bitbonsai/mcpvault",
    "@playwright/mcp",
    "playwright-mcp",
    "serena start-mcp-server",
    "serena\\start-mcp-server",
    "oraios/serena",
)

WINDOWS_PLATFORM_TAG: str = "win32"

PROCESS_LIST_POWERSHELL_COMMAND: str = (
    "Get-CimInstance Win32_Process | "
    "Select-Object ProcessId,ParentProcessId,CommandLine | "
    "ConvertTo-Json -Compress"
)

TASKKILL_EXECUTABLE_NAME: str = "taskkill"
ALL_TASKKILL_ARGUMENTS: tuple[str, ...] = ("/F", "/T", "/PID")

PROCESS_LIST_SUBPROCESS_TIMEOUT_SECONDS: int = 60
TASKKILL_SUBPROCESS_TIMEOUT_SECONDS: int = 30

JSON_INDENT_SPACES: int = 2
UTF8_ENCODING: str = "utf-8"
