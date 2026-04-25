"""Failing-first tests for hook_log_init.

Covers: environment variable verification, idempotent DDL apply, sentinel
insert/select/delete round-trip, and success report format.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from diagnostic import hook_log_init
from config import hook_log_extractor_constants
from config.hook_log_extractor_constants import (
    EXIT_CODE_ENVIRONMENT_MISSING,
    NEON_DATABASE_URL_ENVIRONMENT_VARIABLE,
    OUTCOME_INIT_PROBE,
)


def test_main_exits_1_when_neon_database_url_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(NEON_DATABASE_URL_ENVIRONMENT_VARIABLE, raising=False)

    exit_code = hook_log_init.main()

    assert exit_code == EXIT_CODE_ENVIRONMENT_MISSING
    captured = capsys.readouterr()
    assert NEON_DATABASE_URL_ENVIRONMENT_VARIABLE in captured.err


def test_main_exits_1_when_neon_database_url_is_empty_string(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Empty NEON_HOOK_LOGS_DATABASE_URL must fire missing-env branch."""
    monkeypatch.setenv(NEON_DATABASE_URL_ENVIRONMENT_VARIABLE, "")

    exit_code = hook_log_init.main()

    assert exit_code == EXIT_CODE_ENVIRONMENT_MISSING
    captured = capsys.readouterr()
    assert NEON_DATABASE_URL_ENVIRONMENT_VARIABLE in captured.err


def test_main_exits_1_when_neon_database_url_is_whitespace_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Whitespace-only NEON_HOOK_LOGS_DATABASE_URL must fire missing-env branch."""
    monkeypatch.setenv(NEON_DATABASE_URL_ENVIRONMENT_VARIABLE, "   ")

    exit_code = hook_log_init.main()

    assert exit_code == EXIT_CODE_ENVIRONMENT_MISSING
    captured = capsys.readouterr()
    assert NEON_DATABASE_URL_ENVIRONMENT_VARIABLE in captured.err


def test_apply_schema_executes_ddl_from_schema_sql() -> None:
    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    hook_log_init.apply_schema(fake_connection)

    all_executed_statements = [
        each_call.args[0] for each_call in fake_cursor.execute.call_args_list
    ]
    joined_schema_text = "\n".join(all_executed_statements)
    assert "hook_events" in joined_schema_text
    assert "CREATE TABLE IF NOT EXISTS" in joined_schema_text
    assert "blocked_commands" in joined_schema_text


def test_run_sentinel_round_trip_inserts_selects_and_deletes() -> None:
    fake_cursor = MagicMock()
    fake_cursor.fetchone.side_effect = [(1,), (1,)]
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    hook_log_init.run_sentinel_round_trip(fake_connection)

    all_executed_statements = [
        each_call.args[0].upper() for each_call in fake_cursor.execute.call_args_list
    ]
    assert any("INSERT" in each_statement for each_statement in all_executed_statements)
    assert any("SELECT" in each_statement for each_statement in all_executed_statements)
    assert any("DELETE" in each_statement for each_statement in all_executed_statements)


def test_run_sentinel_round_trip_uses_init_probe_outcome() -> None:
    fake_cursor = MagicMock()
    fake_cursor.fetchone.side_effect = [(1,), (1,)]
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    hook_log_init.run_sentinel_round_trip(fake_connection)

    all_call_parameters = [
        each_call.args for each_call in fake_cursor.execute.call_args_list
    ]
    joined_parameter_text = " ".join(
        str(each_parameter_tuple) for each_parameter_tuple in all_call_parameters
    )
    assert OUTCOME_INIT_PROBE in joined_parameter_text


def test_print_success_report_includes_host_table_and_rowcount(
    capsys: pytest.CaptureFixture[str],
) -> None:
    hook_log_init.print_success_report(
        neon_host="ep-fake-neon.aws.neon.tech",
        table_name="hook_events",
        row_count=42,
    )

    captured = capsys.readouterr()
    assert "ep-fake-neon.aws.neon.tech" in captured.out
    assert "hook_events" in captured.out
    assert "42" in captured.out


def test_main_happy_path_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        NEON_DATABASE_URL_ENVIRONMENT_VARIABLE,
        "postgres://u:p@ep-fake-host.aws.neon.tech/db",
    )

    fake_cursor = MagicMock()
    fake_cursor.fetchone.side_effect = [(1,), (1,), (5,)]
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(hook_log_init, "connect_to_neon", return_value=fake_connection):
        exit_code = hook_log_init.main()

    assert exit_code == 0


def test_connect_to_neon_raises_when_psycopg_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        NEON_DATABASE_URL_ENVIRONMENT_VARIABLE,
        "postgres://u:p@ep-fake-host.aws.neon.tech/db",
    )

    with patch.object(hook_log_init, "psycopg", None):
        with pytest.raises(hook_log_init.MissingPsycopgDependencyError):
            hook_log_init.connect_to_neon()


def test_run_sentinel_round_trip_raises_when_select_returns_nothing() -> None:
    fake_cursor = MagicMock()
    fake_cursor.fetchone.side_effect = [(1,), None]
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with pytest.raises(RuntimeError):
        hook_log_init.run_sentinel_round_trip(fake_connection)


def test_run_sentinel_round_trip_raises_when_select_returns_wrong_id() -> None:
    fake_cursor = MagicMock()
    fake_cursor.fetchone.side_effect = [(1,), (999,)]
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with pytest.raises(RuntimeError):
        hook_log_init.run_sentinel_round_trip(fake_connection)


def test_run_sentinel_round_trip_raises_when_insert_returns_no_row() -> None:
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = None
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with pytest.raises(RuntimeError):
        hook_log_init.run_sentinel_round_trip(fake_connection)


def test_claude_home_resolver_falls_back_to_home_when_env_var_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty CLAUDE_HOME must fall back to ~/.claude (not process CWD)."""
    monkeypatch.setenv("CLAUDE_HOME", "")

    resolved_home = hook_log_extractor_constants._resolve_claude_home_directory()

    expected_home = Path.home() / ".claude"
    assert resolved_home == expected_home


def test_claude_home_resolver_falls_back_to_home_when_env_var_is_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace-only CLAUDE_HOME must fall back to ~/.claude."""
    monkeypatch.setenv("CLAUDE_HOME", "   ")

    resolved_home = hook_log_extractor_constants._resolve_claude_home_directory()

    expected_home = Path.home() / ".claude"
    assert resolved_home == expected_home


def test_claude_home_resolver_honors_explicit_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit CLAUDE_HOME path must win over the home fallback."""
    explicit_claude_home = tmp_path / "explicit-claude-home"
    monkeypatch.setenv("CLAUDE_HOME", str(explicit_claude_home))

    resolved_home = hook_log_extractor_constants._resolve_claude_home_directory()

    assert resolved_home == explicit_claude_home
