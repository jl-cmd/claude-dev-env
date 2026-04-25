"""Constants for the hook-log extractor and init scripts.

Centralizes all named values used by ``hook_log_extractor.py`` and
``hook_log_init.py`` so that production modules carry zero magic values.
"""

from __future__ import annotations

import os
from pathlib import Path

COMMAND_EXCERPT_MAX_CHARACTERS: int = 300
STDOUT_EXCERPT_MAX_CHARACTERS: int = 500
STDERR_EXCERPT_MAX_CHARACTERS: int = 500

INSERT_BATCH_SIZE: int = 500
CONNECT_TIMEOUT_SECONDS: int = 5

def _resolve_claude_home_directory() -> Path:
    """Return the root of the local ``~/.claude`` tree, honoring ``CLAUDE_HOME``.

    An unset, empty, or whitespace-only ``CLAUDE_HOME`` falls back to
    ``~/.claude`` so state and transcript paths do not silently resolve
    to the process working directory.
    """
    claude_home_override = os.environ.get("CLAUDE_HOME", "").strip()
    if claude_home_override:
        return Path(claude_home_override).expanduser()
    return Path.home() / ".claude"


OFFSET_STATE_FILE: str = str(
    _resolve_claude_home_directory()
    / "logs"
    / "hooks"
    / ".state"
    / "offsets.json"
)
OFFLINE_WARNING_LOG: str = str(
    _resolve_claude_home_directory() / "logs" / "hook-extractor.log"
)
PROJECTS_TRANSCRIPT_ROOT: str = str(_resolve_claude_home_directory() / "projects")

NEON_DATABASE_URL_ENVIRONMENT_VARIABLE: str = "NEON_HOOK_LOGS_DATABASE_URL"

ATTACHMENT_TYPE_PREFIX: str = "hook_"
TOP_LEVEL_ATTACHMENT_TYPE: str = "attachment"

ATTACHMENT_TYPE_HOOK_SUCCESS: str = "hook_success"
ATTACHMENT_TYPE_HOOK_BLOCKING_ERROR: str = "hook_blocking_error"
ATTACHMENT_TYPE_HOOK_SYSTEM_MESSAGE: str = "hook_system_message"
ATTACHMENT_TYPE_HOOK_ADDITIONAL_CONTEXT: str = "hook_additional_context"

OUTCOME_SUCCESS: str = "success"
OUTCOME_BLOCKED: str = "blocked"
OUTCOME_NON_BLOCKING_ERROR: str = "non_blocking_error"
OUTCOME_SYSTEM_MESSAGE: str = "system_message"
OUTCOME_ADDED_CONTEXT: str = "added_context"
OUTCOME_INIT_PROBE: str = "init_probe"

OUTCOME_BY_ATTACHMENT_TYPE: dict[str, str] = {
    ATTACHMENT_TYPE_HOOK_SUCCESS: OUTCOME_SUCCESS,
    ATTACHMENT_TYPE_HOOK_BLOCKING_ERROR: OUTCOME_BLOCKED,
    "hook_non_blocking_error": OUTCOME_NON_BLOCKING_ERROR,
    ATTACHMENT_TYPE_HOOK_SYSTEM_MESSAGE: OUTCOME_SYSTEM_MESSAGE,
    ATTACHMENT_TYPE_HOOK_ADDITIONAL_CONTEXT: OUTCOME_ADDED_CONTEXT,
}

HOOK_CATEGORY_UNCATEGORIZED: str = "uncategorized"

KNOWN_HOOK_CATEGORIES: frozenset[str] = frozenset(
    {
        "advisory",
        "blocking",
        "config",
        "context",
        "diagnostic",
        "git-hooks",
        "github-action",
        "lifecycle",
        "notification",
        "session",
        "system",
        "validation",
        "validators",
        "workflow",
        "worktree",
    },
)

HOOK_NAME_TOOL_SEPARATOR: str = ":"

SCHEMA_RELATIVE_PATH: str = "schema.sql"
QUERIES_DIRECTORY_NAME: str = "queries"
SQL_FILE_EXTENSION: str = ".sql"

DEFAULT_QUERY_FOR_SUMMARY: str = "top_blockers_last_24_hours"

JSONL_FILE_GLOB: str = "*.jsonl"

FLAG_INCREMENTAL: str = "--incremental"
FLAG_FULL_REBUILD: str = "--full-rebuild"
FLAG_SUMMARY: str = "--summary"
FLAG_QUERY: str = "--query"

EXIT_CODE_SUCCESS: int = 0
EXIT_CODE_ENVIRONMENT_MISSING: int = 1
EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING: int = 0
EXIT_CODE_UNKNOWN_QUERY: int = 2

QUERY_NAME_PATTERN: str = r"[a-z0-9_]+"

SENTINEL_SESSION_ID: str = "__init_probe_session__"
SENTINEL_HOOK_EVENT: str = "InitProbe"
SENTINEL_HOOK_NAME: str = "init_probe"
SENTINEL_SOURCE_PATH: str = "__init_probe__"
SENTINEL_SOURCE_LINE_NUMBER: int = 0

SUMMARY_COLUMN_HEADINGS: tuple[str, str, str, str] = (
    "hook_name",
    "hook_category",
    "block_count_last_24_hours",
    "top_blocked_command_preview",
)

SUMMARY_NO_NEW_BLOCKS_MESSAGE: str = "No new blocks since last run."

QUERY_NO_ROWS_RETURNED_MESSAGE: str = "No rows returned."

TOP_BLOCKED_COMMAND_PREVIEW_MAX_CHARACTERS: int = 80

HOOK_EVENTS_TABLE_NAME: str = "hook_events"

HOOK_EVENTS_INSERT_SQL: str = (
    "INSERT INTO hook_events ("
    "event_timestamp, session_id, cwd, git_branch, hook_event, hook_name, "
    "hook_category, script_path, tool_name, tool_use_id, outcome, exit_code, "
    "duration_ms, command_excerpt, stdout_excerpt, stderr_excerpt, "
    "source_jsonl_path, source_line_number"
    ") VALUES ("
    "%(event_timestamp)s, %(session_id)s, %(cwd)s, %(git_branch)s, "
    "%(hook_event)s, %(hook_name)s, %(hook_category)s, %(script_path)s, "
    "%(tool_name)s, %(tool_use_id)s, %(outcome)s, %(exit_code)s, "
    "%(duration_ms)s, %(command_excerpt)s, %(stdout_excerpt)s, "
    "%(stderr_excerpt)s, %(source_jsonl_path)s, %(source_line_number)s"
    ") ON CONFLICT (source_jsonl_path, source_line_number) DO NOTHING"
)

HOOK_EVENTS_TRUNCATE_SQL: str = "TRUNCATE TABLE hook_events RESTART IDENTITY"

HOOK_EVENTS_ROW_COUNT_SQL: str = "SELECT COUNT(*) FROM hook_events"

SENTINEL_INSERT_SQL: str = (
    "INSERT INTO hook_events ("
    "event_timestamp, session_id, hook_event, hook_name, hook_category, "
    "outcome, source_jsonl_path, source_line_number"
    ") VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s) RETURNING id"
)

SENTINEL_SELECT_SQL: str = "SELECT id FROM hook_events WHERE id = %s"

SENTINEL_DELETE_SQL: str = "DELETE FROM hook_events WHERE id = %s"

TOP_BLOCKERS_LAST_24_HOURS_SQL: str = (
    "SELECT hook_name, hook_category, COUNT(*) AS block_count, "
    "MIN(COALESCE(command_excerpt, stdout_excerpt, stderr_excerpt, '')) "
    "AS top_blocked_command_preview "
    "FROM hook_events WHERE outcome = 'blocked' "
    "AND event_timestamp >= (NOW() - INTERVAL '1 day') "
    "GROUP BY hook_name, hook_category "
    "ORDER BY block_count DESC LIMIT 10"
)

EMPTY_STRING: str = ""
NEWLINE_JOINER: str = "\n"
SEMICOLON_SPLIT_TOKEN: str = ";"

HOOKS_DIRECTORY_TOKEN: str = "/hooks/"

SCRIPT_PATH_PYTHON_PREFIXES: tuple[str, ...] = ("python3 ", "python ")

SUMMARY_TABLE_COLUMN_GAP: str = "  "

CATEGORY_PATH_MINIMUM_PARTS: int = 2
OFFSETS_JSON_INDENT: int = 2

MISSING_ENVIRONMENT_VARIABLE_PREFIX: str = "Missing required environment variable: "
SUCCESS_REPORT_HEADER: str = "Hook-log init succeeded."
NEON_HOST_REPORT_LABEL: str = "Neon host:"
TABLE_REPORT_LABEL: str = "Table:"
ROW_COUNT_REPORT_LABEL: str = "Row count:"
UNKNOWN_HOST_PLACEHOLDER: str = "unknown"
SENTINEL_HOOK_CATEGORY: str = "diagnostic"

MISSING_PSYCOPG_WARNING_LABEL: str = "missing_psycopg"
MISSING_NEON_DATABASE_URL_WARNING_LABEL: str = "missing_neon_database_url"
LEGACY_OFFSETS_FORMAT_WARNING_LABEL: str = "legacy_offsets_format"

SENTINEL_SELECT_FAILURE_MESSAGE: str = (
    "Sentinel SELECT did not return the inserted id; round-trip failed."
)

SENTINEL_INSERT_FAILURE_MESSAGE: str = (
    "Sentinel INSERT did not return a row; round-trip failed."
)

BYTE_OFFSET_KEY: str = "byte_offset"
LINE_NUMBER_KEY: str = "line_number"

UNKNOWN_QUERY_MESSAGE_PREFIX: str = "Unknown query: "
INVALID_QUERY_NAME_MESSAGE_PREFIX: str = "Invalid query name: "

BWS_EXECUTABLE_NAME: str = "bws"
BWS_ACCESS_TOKEN_ENV_VAR: str = "BWS_ACCESS_TOKEN"
BWS_RUN_SEPARATOR: str = "--"
BWS_RUN_SUBCOMMAND: str = "run"
STOP_WRAPPER_EXTRACTOR_SCRIPT_NAME: str = "hook_log_extractor.py"

LOCK_MAXIMUM_RETRY_COUNT: int = 30
LOCK_RETRY_SLEEP_SECONDS: float = 0.1

