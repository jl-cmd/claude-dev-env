#!/usr/bin/env python3
"""Initialize the Neon schema for hook-log diagnostics.

Verifies required environment variables, opens a psycopg connection,
applies the idempotent DDL from ``schema.sql``, runs a sentinel
insert/select/delete round-trip to prove read-write parity, and prints
a success report with the Neon host, table name, and row count.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import psycopg
except ImportError:
    psycopg = None

from config.hook_log_extractor_constants import (
    CONNECT_TIMEOUT_SECONDS,
    EXIT_CODE_ENVIRONMENT_MISSING,
    EXIT_CODE_SUCCESS,
    HOOK_EVENTS_ROW_COUNT_SQL,
    HOOK_EVENTS_TABLE_NAME,
    MISSING_ENVIRONMENT_VARIABLE_PREFIX,
    MISSING_PSYCOPG_WARNING_LABEL,
    NEON_DATABASE_URL_ENVIRONMENT_VARIABLE,
    NEON_HOST_REPORT_LABEL,
    OUTCOME_INIT_PROBE,
    ROW_COUNT_REPORT_LABEL,
    SCHEMA_RELATIVE_PATH,
    SEMICOLON_SPLIT_TOKEN,
    SENTINEL_DELETE_SQL,
    SENTINEL_HOOK_CATEGORY,
    SENTINEL_HOOK_EVENT,
    SENTINEL_HOOK_NAME,
    SENTINEL_INSERT_FAILURE_MESSAGE,
    SENTINEL_INSERT_SQL,
    SENTINEL_SELECT_FAILURE_MESSAGE,
    SENTINEL_SELECT_SQL,
    SENTINEL_SESSION_ID,
    SENTINEL_SOURCE_LINE_NUMBER,
    SENTINEL_SOURCE_PATH,
    SUCCESS_REPORT_HEADER,
    TABLE_REPORT_LABEL,
    UNKNOWN_HOST_PLACEHOLDER,
)


class MissingPsycopgDependencyError(RuntimeError):
    """Raised when the psycopg driver is not installed in the interpreter."""


def verify_environment_variables() -> list[str]:
    """Return names of required env vars that are unset; empty list when all present.

    Only ``NEON_HOOK_LOGS_DATABASE_URL`` is verified here. ``bws run``
    intentionally strips ``BWS_ACCESS_TOKEN`` from the child environment
    to prevent subprocess credential leakage; checking for it inside a
    child process invoked via ``bws run -- python hook_log_init.py``
    would therefore always fail even when the machine is configured
    correctly. The one-time ``setx BWS_ACCESS_TOKEN`` prerequisite is
    documented in ``packages/claude-dev-env/commands/hook-log-init.md``.
    """
    all_missing_variable_names: list[str] = []
    raw_database_url_value = os.environ.get(NEON_DATABASE_URL_ENVIRONMENT_VARIABLE)
    if raw_database_url_value is None or raw_database_url_value.strip() == "":
        all_missing_variable_names.append(NEON_DATABASE_URL_ENVIRONMENT_VARIABLE)
    return all_missing_variable_names


def _schema_file_path() -> Path:
    """Return the absolute path to the companion ``schema.sql`` file."""
    return Path(__file__).resolve().parent / SCHEMA_RELATIVE_PATH


def _split_ddl_statements(schema_text: str) -> list[str]:
    """Split a DDL file on semicolons and drop empty trailing fragments."""
    all_raw_fragments = schema_text.split(SEMICOLON_SPLIT_TOKEN)
    all_trimmed_statements = [
        each_fragment.strip() for each_fragment in all_raw_fragments
    ]
    return [
        each_statement for each_statement in all_trimmed_statements if each_statement
    ]


def apply_schema(neon_connection: object) -> None:
    """Execute the idempotent DDL from ``schema.sql`` on the given connection."""
    schema_text = _schema_file_path().read_text(encoding="utf-8")
    all_ddl_statements = _split_ddl_statements(schema_text)
    with neon_connection.cursor() as neon_cursor:
        for each_statement in all_ddl_statements:
            neon_cursor.execute(each_statement)
    neon_connection.commit()


def run_sentinel_round_trip(neon_connection: object) -> None:
    """Insert a sentinel row, select it back by id, verify it, then delete it."""
    with neon_connection.cursor() as neon_cursor:
        neon_cursor.execute(
            SENTINEL_INSERT_SQL,
            (
                SENTINEL_SESSION_ID,
                SENTINEL_HOOK_EVENT,
                SENTINEL_HOOK_NAME,
                SENTINEL_HOOK_CATEGORY,
                OUTCOME_INIT_PROBE,
                SENTINEL_SOURCE_PATH,
                SENTINEL_SOURCE_LINE_NUMBER,
            ),
        )
        sentinel_row = neon_cursor.fetchone()
        if sentinel_row is None:
            raise RuntimeError(SENTINEL_INSERT_FAILURE_MESSAGE)
        sentinel_id = sentinel_row[0]
        neon_cursor.execute(SENTINEL_SELECT_SQL, (sentinel_id,))
        fetched_row = neon_cursor.fetchone()
        if fetched_row is None or fetched_row[0] != sentinel_id:
            raise RuntimeError(SENTINEL_SELECT_FAILURE_MESSAGE)
        neon_cursor.execute(SENTINEL_DELETE_SQL, (sentinel_id,))
    neon_connection.commit()


def _extract_host_from_database_url(database_url: str) -> str:
    """Return the hostname portion of a Postgres connection URL."""
    parsed_url = urlparse(database_url)
    return parsed_url.hostname or UNKNOWN_HOST_PLACEHOLDER


def print_success_report(neon_host: str, table_name: str, row_count: int) -> None:
    """Print a 4-line success report with Neon host, table name, and row count."""
    print(SUCCESS_REPORT_HEADER)
    print(f"{NEON_HOST_REPORT_LABEL} {neon_host}")
    print(f"{TABLE_REPORT_LABEL} {table_name}")
    print(f"{ROW_COUNT_REPORT_LABEL} {row_count}")


def connect_to_neon() -> object:
    """Open a psycopg v3 connection using the configured Neon database URL.

    Raises ``MissingPsycopgDependencyError`` when psycopg is not installed
    so the caller can surface a clear actionable message.
    """
    if psycopg is None:
        raise MissingPsycopgDependencyError(MISSING_PSYCOPG_WARNING_LABEL)
    database_url = os.environ[NEON_DATABASE_URL_ENVIRONMENT_VARIABLE]
    return psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS)


def _fetch_row_count(neon_connection: object) -> int:
    """Return the current row count of the ``hook_events`` table."""
    with neon_connection.cursor() as neon_cursor:
        neon_cursor.execute(HOOK_EVENTS_ROW_COUNT_SQL)
        row_count_row = neon_cursor.fetchone()
    return int(row_count_row[0]) if row_count_row else 0


def _print_missing_environment_variables(all_missing_variable_names: list[str]) -> None:
    """Write one stderr line per missing environment variable name."""
    for each_missing_name in all_missing_variable_names:
        print(
            f"{MISSING_ENVIRONMENT_VARIABLE_PREFIX}{each_missing_name}",
            file=sys.stderr,
        )


def main() -> int:
    """Entry point for the ``/hook-log-init`` slash command."""
    all_missing_variable_names = verify_environment_variables()
    if all_missing_variable_names:
        _print_missing_environment_variables(all_missing_variable_names)
        return EXIT_CODE_ENVIRONMENT_MISSING
    neon_connection = connect_to_neon()
    try:
        apply_schema(neon_connection)
        run_sentinel_round_trip(neon_connection)
        row_count_value = _fetch_row_count(neon_connection)
        neon_host_string = _extract_host_from_database_url(
            os.environ[NEON_DATABASE_URL_ENVIRONMENT_VARIABLE],
        )
        print_success_report(
            neon_host=neon_host_string,
            table_name=HOOK_EVENTS_TABLE_NAME,
            row_count=row_count_value,
        )
        return EXIT_CODE_SUCCESS
    finally:
        try:
            neon_connection.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
