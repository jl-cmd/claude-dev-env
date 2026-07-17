"""Constants for lean MCP policy application and process-count measurement."""

from __future__ import annotations

import os

UTF8_ENCODING: str = "utf-8"
JSON_INDENT_SPACES: int = 2
BACKUP_TIMESTAMP_FORMAT: str = "%Y%m%dT%H%M%SZ"
BACKUP_SUFFIX_SEPARATOR: str = ".bak-"
COMMAND_LINE_JOIN_SEPARATOR: str = " "

CLAUDE_USER_HOME = os.path.expanduser("~")
CLAUDE_JSON_PATH = os.path.join(CLAUDE_USER_HOME, ".claude.json")
CLAUDE_DOT_CLAUDE_JSON_PATH = os.path.join(
    CLAUDE_USER_HOME, ".claude", ".claude.json"
)
CLAUDE_SETTINGS_JSON_PATH = os.path.join(
    CLAUDE_USER_HOME, ".claude", "settings.json"
)
CLAUDE_SETTINGS_LOCAL_JSON_PATH = os.path.join(
    CLAUDE_USER_HOME, ".claude", "settings.local.json"
)
CLAUDE_DESKTOP_CONFIG_PATH = os.path.join(
    os.environ.get("APPDATA", ""),
    "Claude",
    "claude_desktop_config.json",
)
GROK_CONFIG_TOML_PATH = os.path.join(CLAUDE_USER_HOME, ".grok", "config.toml")

MCP_SERVERS_KEY: str = "mcpServers"
ENABLED_PLUGINS_KEY: str = "enabledPlugins"
SERVER_TYPE_KEY: str = "type"
SERVER_COMMAND_KEY: str = "command"
SERVER_ARGS_KEY: str = "args"
SERVER_URL_KEY: str = "url"
SERVER_ALWAYS_LOAD_KEY: str = "alwaysLoad"
HTTP_SERVER_TYPE: str = "http"

ALL_HEAVY_STDIO_MCP_NAME_MARKERS: tuple[str, ...] = (
    "obsidian",
    "mcpvault",
    "serena",
    "playwright",
)

ALL_HEAVY_STDIO_COMMAND_MARKERS: tuple[str, ...] = (
    "mcpvault",
    "@bitbonsai/mcpvault",
    "@playwright/mcp",
    "playwright-mcp",
    "serena",
    "oraios/serena",
)

ALL_PLAYWRIGHT_PLUGIN_KEYS: tuple[str, ...] = (
    "playwright@claude-plugins-official",
)

GROK_COMPAT_CLAUDE_SECTION_HEADER: str = "[compat.claude]"
GROK_COMPAT_CLAUDE_MCPS_DISABLED_LINE: str = "mcps = false"
GROK_COMPAT_CLAUDE_BLOCK: str = (
    f"{GROK_COMPAT_CLAUDE_SECTION_HEADER}\n"
    f"{GROK_COMPAT_CLAUDE_MCPS_DISABLED_LINE}\n"
)

PROCESS_COUNT_POWERSHELL_COMMAND: str = (
    "$allProcesses = Get-CimInstance Win32_Process | "
    "Select-Object ProcessId,Name,CommandLine; "
    "$mcpvault = @($allProcesses | Where-Object { "
    "$_.CommandLine -and ($_.CommandLine -match 'mcpvault') }); "
    "$playwright = @($allProcesses | Where-Object { "
    "$_.CommandLine -and ($_.CommandLine -match 'playwright') "
    "-and ($_.CommandLine -match 'mcp') }); "
    "$serena = @($allProcesses | Where-Object { "
    "$_.CommandLine -and ($_.CommandLine -match 'serena') }); "
    "$node = @($allProcesses | Where-Object { $_.Name -eq 'node.exe' }); "
    "[pscustomobject]@{"
    "mcpvault_cmdline=$mcpvault.Count; "
    "playwright_mcp=$playwright.Count; "
    "serena=$serena.Count; "
    "node=$node.Count; "
    "total=$allProcesses.Count"
    "} | ConvertTo-Json -Compress"
)

PROCESS_COUNT_SUBPROCESS_TIMEOUT_SECONDS: int = 60
TEARDOWN_DEADLINE_SECONDS: int = 60
RECIPE_CHILD_SETTLE_SECONDS: float = 0.5
RECIPE_POLL_INTERVAL_SECONDS: float = 0.25
RECIPE_CHILD_KILL_WAIT_SECONDS: int = 5
ELAPSED_SECONDS_PRECISION: int = 3
MCP_MARKER_LABEL: str = "mcpvault-recipe-probe"
SESSION_ID_FOR_RECIPE: str = "recipe-mcp-teardown"

ALL_EMPTY_PROCESS_COUNTS: dict[str, int] = {
    "mcpvault_cmdline": 0,
    "playwright_mcp": 0,
    "serena": 0,
    "node": 0,
    "total": 0,
}
