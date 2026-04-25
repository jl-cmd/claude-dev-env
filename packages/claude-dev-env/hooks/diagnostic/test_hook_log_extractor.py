"""Failing-first tests for hook_log_extractor.

Covers category derivation (15 known + uncategorized fallback), outcome
mapping (4 attachment types), excerpt truncation, offset advance,
idempotence via ON CONFLICT, offline graceful fallback, and batched
INSERT shape. psycopg is mocked at the connect boundary.
"""

from __future__ import annotations

import contextlib
import errno
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from diagnostic import hook_log_extractor
from config.hook_log_extractor_constants import (
    COMMAND_EXCERPT_MAX_CHARACTERS,
    EXIT_CODE_UNKNOWN_QUERY,
    HOOK_CATEGORY_UNCATEGORIZED,
    KNOWN_HOOK_CATEGORIES,
    NEON_DATABASE_URL_ENVIRONMENT_VARIABLE,
    OUTCOME_ADDED_CONTEXT,
    OUTCOME_BLOCKED,
    OUTCOME_NON_BLOCKING_ERROR,
    OUTCOME_SUCCESS,
    OUTCOME_SYSTEM_MESSAGE,
    STDERR_EXCERPT_MAX_CHARACTERS,
    STDOUT_EXCERPT_MAX_CHARACTERS,
)


def _make_success_line(
    session_id: str = "session-alpha",
    hook_name: str = "PreToolUse:Bash",
    hook_event: str = "PreToolUse",
    tool_use_id: str = "toolu_001",
    command: str = "python C:/Users/jon/.claude/hooks/blocking/destructive_command_blocker.py",
    stdout: str = "ok\n",
    stderr: str = "",
    exit_code: int = 0,
    duration_ms: int = 42,
    timestamp: str = "2026-04-24T13:32:07.978Z",
    cwd: str = "Y:\\Projects\\repo",
    git_branch: str = "main",
) -> str:
    record = {
        "type": "attachment",
        "attachment": {
            "type": "hook_success",
            "hookName": hook_name,
            "hookEvent": hook_event,
            "toolUseID": tool_use_id,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "exitCode": exit_code,
            "durationMs": duration_ms,
        },
        "timestamp": timestamp,
        "sessionId": session_id,
        "cwd": cwd,
        "gitBranch": git_branch,
    }
    return json.dumps(record)


def _make_blocking_line(
    session_id: str = "session-alpha",
    hook_name: str = "PreToolUse:Bash",
    hook_event: str = "PreToolUse",
    tool_use_id: str = "toolu_002",
    blocking_message: str = "blocked for reason",
    command: str = "python C:/Users/jon/.claude/hooks/blocking/content_search_to_zoekt_redirector.py",
    timestamp: str = "2026-04-24T13:32:54.293Z",
    cwd: str = "Y:\\Projects\\repo",
    git_branch: str = "main",
) -> str:
    record = {
        "type": "attachment",
        "attachment": {
            "type": "hook_blocking_error",
            "hookName": hook_name,
            "hookEvent": hook_event,
            "toolUseID": tool_use_id,
            "blockingError": {
                "blockingError": blocking_message,
                "command": command,
            },
        },
        "timestamp": timestamp,
        "sessionId": session_id,
        "cwd": cwd,
        "gitBranch": git_branch,
    }
    return json.dumps(record)


def _make_system_message_line(
    session_id: str = "session-alpha",
    hook_name: str = "PreToolUse:Bash",
    hook_event: str = "PreToolUse",
    tool_use_id: str = "toolu_003",
    content: str = "[destructive-gate] blocked",
    timestamp: str = "2026-04-24T13:32:54.293Z",
    cwd: str = "Y:\\Projects\\repo",
    git_branch: str = "main",
) -> str:
    record = {
        "type": "attachment",
        "attachment": {
            "type": "hook_system_message",
            "hookName": hook_name,
            "hookEvent": hook_event,
            "toolUseID": tool_use_id,
            "content": content,
        },
        "timestamp": timestamp,
        "sessionId": session_id,
        "cwd": cwd,
        "gitBranch": git_branch,
    }
    return json.dumps(record)


def _make_additional_context_line(
    session_id: str = "session-alpha",
    hook_name: str = "PreToolUse:Bash",
    hook_event: str = "PreToolUse",
    tool_use_id: str = "toolu_004",
    content: list[str] | None = None,
    timestamp: str = "2026-04-24T13:32:54.293Z",
    cwd: str = "Y:\\Projects\\repo",
    git_branch: str = "main",
) -> str:
    record = {
        "type": "attachment",
        "attachment": {
            "type": "hook_additional_context",
            "hookName": hook_name,
            "hookEvent": hook_event,
            "toolUseID": tool_use_id,
            "content": content or ["extra context"],
        },
        "timestamp": timestamp,
        "sessionId": session_id,
        "cwd": cwd,
        "gitBranch": git_branch,
    }
    return json.dumps(record)


@pytest.mark.parametrize(
    "expected_category",
    sorted(KNOWN_HOOK_CATEGORIES),
)
def test_derive_category_accepts_each_known_category(expected_category: str) -> None:
    script_path = f"python C:/Users/jon/.claude/hooks/{expected_category}/some_hook.py"
    assert hook_log_extractor.derive_category(script_path) == expected_category


def test_derive_category_returns_uncategorized_for_unknown_parent() -> None:
    script_path = "python C:/Users/jon/.claude/hooks/unheard_of_bucket/some_hook.py"
    assert (
        hook_log_extractor.derive_category(script_path) == HOOK_CATEGORY_UNCATEGORIZED
    )


def test_derive_category_returns_uncategorized_for_empty_path() -> None:
    assert hook_log_extractor.derive_category(None) == HOOK_CATEGORY_UNCATEGORIZED
    assert hook_log_extractor.derive_category("") == HOOK_CATEGORY_UNCATEGORIZED


def test_derive_category_handles_windows_backslash_paths() -> None:
    script_path = "python C:\\Users\\jon\\.claude\\hooks\\blocking\\destructive_command_blocker.py"
    assert hook_log_extractor.derive_category(script_path) == "blocking"


def test_derive_category_strips_python_launcher_prefix() -> None:
    script_path = "python3 /home/jon/.claude/hooks/session/code_rules_reminder.py"
    assert hook_log_extractor.derive_category(script_path) == "session"


def test_derive_outcome_maps_hook_success() -> None:
    assert hook_log_extractor.derive_outcome("hook_success") == OUTCOME_SUCCESS


def test_derive_outcome_maps_hook_blocking_error() -> None:
    assert hook_log_extractor.derive_outcome("hook_blocking_error") == OUTCOME_BLOCKED


def test_derive_outcome_maps_hook_system_message() -> None:
    assert (
        hook_log_extractor.derive_outcome("hook_system_message")
        == OUTCOME_SYSTEM_MESSAGE
    )


def test_derive_outcome_maps_hook_additional_context() -> None:
    assert (
        hook_log_extractor.derive_outcome("hook_additional_context")
        == OUTCOME_ADDED_CONTEXT
    )


def test_derive_outcome_maps_hook_non_blocking_error() -> None:
    assert (
        hook_log_extractor.derive_outcome("hook_non_blocking_error")
        == OUTCOME_NON_BLOCKING_ERROR
    )


def test_iter_attachment_records_skips_unknown_hook_attachment_type(
    tmp_path: Path,
) -> None:
    jsonl_path = tmp_path / "session-with-unknown-hook-type.jsonl"
    unknown_type_record = {
        "type": "attachment",
        "attachment": {
            "type": "hook_future_unknown_variant",
            "hookName": "PreToolUse:Bash",
            "hookEvent": "PreToolUse",
        },
        "timestamp": "2026-04-24T13:32:54.293Z",
        "sessionId": "session-alpha",
        "cwd": "Y:/Projects/repo",
        "gitBranch": "main",
    }
    jsonl_path.write_text(
        _make_success_line() + "\n" + json.dumps(unknown_type_record) + "\n",
        encoding="utf-8",
    )
    all_yielded_records = list(
        hook_log_extractor.iter_attachment_records_from_file(
            str(jsonl_path),
            start_offset=0,
        ),
    )
    assert len(all_yielded_records) == 1
    first_parsed_record, _line_number, _offset = all_yielded_records[0]
    assert first_parsed_record["attachment"]["type"] == "hook_success"


def test_derive_outcome_raises_on_unknown_type() -> None:
    with pytest.raises(KeyError):
        hook_log_extractor.derive_outcome("hook_something_else")


def test_extract_script_path_from_success_record() -> None:
    record_json = _make_success_line(
        command="python C:/Users/jon/.claude/hooks/blocking/foo.py",
    )
    parsed = json.loads(record_json)
    assert (
        hook_log_extractor.extract_script_path(parsed["attachment"])
        == "C:/Users/jon/.claude/hooks/blocking/foo.py"
    )


def test_extract_script_path_from_blocking_record() -> None:
    record_json = _make_blocking_line(
        command="python3 /home/jon/.claude/hooks/blocking/bar.py",
    )
    parsed = json.loads(record_json)
    assert (
        hook_log_extractor.extract_script_path(parsed["attachment"])
        == "/home/jon/.claude/hooks/blocking/bar.py"
    )


def test_extract_script_path_returns_none_for_system_message() -> None:
    record_json = _make_system_message_line()
    parsed = json.loads(record_json)
    assert hook_log_extractor.extract_script_path(parsed["attachment"]) is None


def test_excerpt_truncation_respects_command_limit() -> None:
    long_command = "x" * (COMMAND_EXCERPT_MAX_CHARACTERS + 50)
    truncated = hook_log_extractor.truncate_command_excerpt(long_command)
    assert len(truncated) == COMMAND_EXCERPT_MAX_CHARACTERS


def test_excerpt_truncation_preserves_short_command() -> None:
    short_command = "python foo.py"
    assert hook_log_extractor.truncate_command_excerpt(short_command) == short_command


def test_excerpt_truncation_handles_none_command() -> None:
    assert hook_log_extractor.truncate_command_excerpt(None) is None


def test_excerpt_truncation_respects_stdout_limit() -> None:
    long_stdout = "y" * (STDOUT_EXCERPT_MAX_CHARACTERS + 100)
    truncated = hook_log_extractor.truncate_stdout_excerpt(long_stdout)
    assert len(truncated) == STDOUT_EXCERPT_MAX_CHARACTERS


def test_excerpt_truncation_respects_stderr_limit() -> None:
    long_stderr = "z" * (STDERR_EXCERPT_MAX_CHARACTERS + 100)
    truncated = hook_log_extractor.truncate_stderr_excerpt(long_stderr)
    assert len(truncated) == STDERR_EXCERPT_MAX_CHARACTERS


def test_build_row_from_success_attachment() -> None:
    record_json = _make_success_line()
    parsed = json.loads(record_json)
    row = hook_log_extractor.build_row_from_attachment(
        parsed_record=parsed,
        source_jsonl_path="C:/fake/path.jsonl",
        source_line_number=1,
    )
    assert row["session_id"] == "session-alpha"
    assert row["hook_event"] == "PreToolUse"
    assert row["hook_name"] == "PreToolUse:Bash"
    assert row["tool_name"] == "Bash"
    assert row["tool_use_id"] == "toolu_001"
    assert row["outcome"] == OUTCOME_SUCCESS
    assert row["exit_code"] == 0
    assert row["duration_ms"] == 42
    assert row["hook_category"] == "blocking"
    assert row["source_jsonl_path"] == "C:/fake/path.jsonl"
    assert row["source_line_number"] == 1


def test_build_row_from_blocking_attachment_has_no_exit_code_or_duration() -> None:
    record_json = _make_blocking_line()
    parsed = json.loads(record_json)
    row = hook_log_extractor.build_row_from_attachment(
        parsed_record=parsed,
        source_jsonl_path="C:/fake/path.jsonl",
        source_line_number=2,
    )
    assert row["outcome"] == OUTCOME_BLOCKED
    assert row["exit_code"] is None
    assert row["duration_ms"] is None
    assert (
        row["stderr_excerpt"] is not None
        and "blocked for reason" in row["stderr_excerpt"]
    )
    assert row["hook_category"] == "blocking"


def test_build_row_from_system_message_uses_content_as_stdout_excerpt() -> None:
    record_json = _make_system_message_line(content="[gate] blocked Bash(grep)")
    parsed = json.loads(record_json)
    row = hook_log_extractor.build_row_from_attachment(
        parsed_record=parsed,
        source_jsonl_path="C:/fake/path.jsonl",
        source_line_number=3,
    )
    assert row["outcome"] == OUTCOME_SYSTEM_MESSAGE
    assert row["stdout_excerpt"] == "[gate] blocked Bash(grep)"


def test_build_row_from_additional_context_joins_list_content() -> None:
    record_json = _make_additional_context_line(content=["first note", "second note"])
    parsed = json.loads(record_json)
    row = hook_log_extractor.build_row_from_attachment(
        parsed_record=parsed,
        source_jsonl_path="C:/fake/path.jsonl",
        source_line_number=4,
    )
    assert row["outcome"] == OUTCOME_ADDED_CONTEXT
    assert row["stdout_excerpt"] is not None
    assert "first note" in row["stdout_excerpt"]
    assert "second note" in row["stdout_excerpt"]


def test_iter_attachment_records_skips_non_attachment_rows(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    lines = [
        json.dumps({"type": "user", "content": "hi"}),
        _make_success_line(),
        json.dumps({"type": "assistant", "content": "hello"}),
        _make_blocking_line(),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    all_parsed_records = list(
        hook_log_extractor.iter_attachment_records_from_file(
            str(jsonl_file), start_offset=0
        ),
    )

    assert len(all_parsed_records) == 2
    first_parsed_record, first_line_number, _first_offset = all_parsed_records[0]
    assert first_parsed_record["attachment"]["type"] == "hook_success"
    assert first_line_number == 2


def test_iter_attachment_records_resumes_from_offset(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    first_line = _make_success_line(tool_use_id="toolu_a")
    second_line = _make_success_line(tool_use_id="toolu_b")
    jsonl_file.write_text(first_line + "\n" + second_line + "\n", encoding="utf-8")
    first_line_byte_length = len((first_line + "\n").encode("utf-8"))

    all_parsed_records = list(
        hook_log_extractor.iter_attachment_records_from_file(
            str(jsonl_file),
            start_offset=first_line_byte_length,
        ),
    )

    assert len(all_parsed_records) == 1
    assert all_parsed_records[0][0]["attachment"]["toolUseID"] == "toolu_b"


def test_iter_attachment_records_ignores_malformed_json(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    lines = [
        "{this is not json",
        _make_success_line(),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    all_parsed_records = list(
        hook_log_extractor.iter_attachment_records_from_file(
            str(jsonl_file), start_offset=0
        ),
    )

    assert len(all_parsed_records) == 1


def test_load_offsets_returns_empty_when_file_missing(tmp_path: Path) -> None:
    missing_state_file = tmp_path / "does_not_exist.json"
    assert hook_log_extractor.load_offsets(str(missing_state_file)) == {}


def test_save_and_load_offsets_round_trips(tmp_path: Path) -> None:
    state_file = tmp_path / "nested" / "state.json"
    original_offset_by_path = {
        "C:/foo.jsonl": {"byte_offset": 100, "line_number": 3},
        "C:/bar.jsonl": {"byte_offset": 250, "line_number": 8},
    }
    hook_log_extractor.save_offsets(str(state_file), original_offset_by_path)
    round_tripped = hook_log_extractor.load_offsets(str(state_file))
    assert round_tripped == original_offset_by_path


def test_insert_rows_batches_uses_execute_values_or_executemany() -> None:
    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    all_rows = [
        {
            "event_timestamp": "2026-04-24T13:32:07.978Z",
            "session_id": "s1",
            "cwd": "c",
            "git_branch": "b",
            "hook_event": "PreToolUse",
            "hook_name": "PreToolUse:Bash",
            "hook_category": "blocking",
            "script_path": "s",
            "tool_name": "Bash",
            "tool_use_id": "t",
            "outcome": OUTCOME_SUCCESS,
            "exit_code": 0,
            "duration_ms": 1,
            "command_excerpt": "cmd",
            "stdout_excerpt": "out",
            "stderr_excerpt": "",
            "source_jsonl_path": "/p.jsonl",
            "source_line_number": each_line_number,
        }
        for each_line_number in range(1, 4)
    ]

    hook_log_extractor.insert_rows_batch(fake_connection, all_rows)

    assert fake_cursor.executemany.called or fake_cursor.execute.called


def test_run_full_extraction_advances_offset(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")

    state_file = tmp_path / "offsets.json"

    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = MagicMock()

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0
    saved_offsets = hook_log_extractor.load_offsets(str(state_file))
    assert str(jsonl_file) in saved_offsets
    assert saved_offsets[str(jsonl_file)]["byte_offset"] > 0
    assert saved_offsets[str(jsonl_file)]["line_number"] >= 1


def test_run_full_extraction_idempotent_when_offset_at_end(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    success_line = _make_success_line() + "\n"
    jsonl_file.write_text(success_line, encoding="utf-8")

    state_file = tmp_path / "offsets.json"
    hook_log_extractor.save_offsets(
        str(state_file),
        {
            str(jsonl_file): {
                "byte_offset": len(success_line.encode("utf-8")),
                "line_number": 1,
            },
        },
    )

    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0
    assert not fake_cursor.executemany.called


def test_run_full_rebuild_clears_offsets_and_truncates(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")

    state_file = tmp_path / "offsets.json"
    hook_log_extractor.save_offsets(
        str(state_file),
        {str(jsonl_file): {"byte_offset": 99999, "line_number": 100}},
    )

    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=True,
        )

    assert exit_code == 0
    all_executed_statements = [
        each_call.args[0] for each_call in fake_cursor.execute.call_args_list
    ]
    assert any(
        "TRUNCATE" in each_statement.upper()
        for each_statement in all_executed_statements
    )
    saved_offsets_after_rebuild = hook_log_extractor.load_offsets(str(state_file))
    rebuilt_entry = saved_offsets_after_rebuild.get(str(jsonl_file), {})
    assert rebuilt_entry.get("byte_offset", 0) > 0
    assert rebuilt_entry.get("line_number", 0) >= 1


def test_offline_fallback_writes_one_log_line_when_connect_fails(
    tmp_path: Path,
) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")

    state_file = tmp_path / "offsets.json"
    warning_log = tmp_path / "hook-extractor.log"

    class _FakeOperationalError(Exception):
        pass

    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise _FakeOperationalError("boom")

    with (
        patch.object(hook_log_extractor, "connect_to_neon", side_effect=_raise),
        patch.object(hook_log_extractor, "is_operational_error", return_value=True),
        patch.object(hook_log_extractor, "OFFLINE_WARNING_LOG", str(warning_log)),
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0
    log_contents = warning_log.read_text(encoding="utf-8")
    assert len(log_contents.strip().splitlines()) == 1


def test_tool_name_extracted_from_hook_name_prefix() -> None:
    assert hook_log_extractor.extract_tool_name("PreToolUse:Bash") == "Bash"
    assert hook_log_extractor.extract_tool_name("PreToolUse:Write|Edit") == "Write|Edit"
    assert hook_log_extractor.extract_tool_name("SessionStart") is None
    assert hook_log_extractor.extract_tool_name("UserPromptSubmit") is None


def test_run_summary_prints_no_new_blocks_when_cursor_empty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = []
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_summary()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No new blocks since last run." in captured.out


def test_run_summary_prints_table_when_rows_returned(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = [
        ("content_search_to_zoekt_redirector.py", "blocking", 7, "Bash(grep foo)"),
    ]
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        exit_code = hook_log_extractor.run_summary()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "content_search_to_zoekt_redirector.py" in captured.out
    assert "blocking" in captured.out
    assert "7" in captured.out


def test_run_full_extraction_returns_zero_when_database_url_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1: Stop-hook path must exit 0 when NEON URL env var is unset."""
    monkeypatch.delenv(NEON_DATABASE_URL_ENVIRONMENT_VARIABLE, raising=False)

    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")
    state_file = tmp_path / "offsets.json"
    warning_log = tmp_path / "hook-extractor.log"

    with patch.object(hook_log_extractor, "OFFLINE_WARNING_LOG", str(warning_log)):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0
    assert warning_log.exists()
    warning_text = warning_log.read_text(encoding="utf-8")
    assert "MissingNeonDatabaseUrlError" in warning_text


def test_run_full_extraction_returns_zero_when_psycopg_not_installed(
    tmp_path: Path,
) -> None:
    """C10: Stop-hook path must exit 0 when psycopg module is absent."""
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")
    state_file = tmp_path / "offsets.json"
    warning_log = tmp_path / "hook-extractor.log"

    with (
        patch.object(hook_log_extractor, "psycopg", None),
        patch.object(hook_log_extractor, "OFFLINE_WARNING_LOG", str(warning_log)),
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0
    assert warning_log.exists()
    warning_text = warning_log.read_text(encoding="utf-8")
    assert "MissingPsycopgDependencyError" in warning_text


def test_offline_warning_line_does_not_leak_exception_message(
    tmp_path: Path,
) -> None:
    """C12: Offline warning log must record only timestamp + class name."""
    warning_log = tmp_path / "hook-extractor.log"

    class _FakeOperationalError(Exception):
        pass

    def _raise_with_sensitive_url(*_args: Any, **_kwargs: Any) -> None:
        raise _FakeOperationalError(
            "connection failed to postgres://user:secret@host/db",
        )

    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")
    state_file = tmp_path / "offsets.json"

    with (
        patch.object(
            hook_log_extractor,
            "connect_to_neon",
            side_effect=_raise_with_sensitive_url,
        ),
        patch.object(hook_log_extractor, "is_operational_error", return_value=True),
        patch.object(hook_log_extractor, "OFFLINE_WARNING_LOG", str(warning_log)),
    ):
        hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    warning_text = warning_log.read_text(encoding="utf-8")
    assert "secret" not in warning_text
    assert "postgres://" not in warning_text


def test_offline_fallback_still_exits_zero_when_warning_log_write_raises(
    tmp_path: Path,
) -> None:
    """Disk-error during warning log write must not break offline-graceful exit.

    The Stop hook contract requires that connect failures log a warning
    and exit with the documented offline status so session shutdown
    never stalls. A read-only filesystem, a missing parent path, or an
    EACCES on the warning log itself must not propagate and must not
    flip the exit code. This test patches ``io.open`` so only the
    OFFLINE_WARNING_LOG path raises, exercising the real inner
    ``try/except OSError`` guard inside ``_append_offline_warning_line``
    rather than monkeypatching the function itself.
    """
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")
    state_file = tmp_path / "offsets.json"
    warning_log = tmp_path / "hook-extractor.log"
    warning_log_path_string = str(warning_log)

    class _FakeOperationalError(Exception):
        pass

    def _raise_connection_failure(*_args: Any, **_kwargs: Any) -> None:
        raise _FakeOperationalError("connect failed")

    real_io_open = hook_log_extractor.io.open

    def _io_open_blocking_warning_log(
        path_argument: Any, *args: Any, **kwargs: Any
    ) -> Any:
        if str(path_argument) == warning_log_path_string:
            raise OSError(errno.EACCES, "permission denied")
        return real_io_open(path_argument, *args, **kwargs)

    with (
        patch.object(
            hook_log_extractor,
            "connect_to_neon",
            side_effect=_raise_connection_failure,
        ),
        patch.object(hook_log_extractor, "is_operational_error", return_value=True),
        patch.object(
            hook_log_extractor, "OFFLINE_WARNING_LOG", warning_log_path_string
        ),
        patch.object(
            hook_log_extractor.io,
            "open",
            side_effect=_io_open_blocking_warning_log,
        ),
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0


def test_main_accepts_incremental_flag_as_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C8: ``--incremental`` must be recognized and route to default extraction."""
    captured_arguments: dict[str, object] = {}

    def _fake_run_full_extraction(
        transcripts_root: str,
        state_file_path: str,
        full_rebuild: bool,
    ) -> int:
        captured_arguments["transcripts_root"] = transcripts_root
        captured_arguments["state_file_path"] = state_file_path
        captured_arguments["full_rebuild"] = full_rebuild
        return 0

    monkeypatch.setattr(sys, "argv", ["hook_log_extractor.py", "--incremental"])
    monkeypatch.setattr(
        hook_log_extractor, "run_full_extraction", _fake_run_full_extraction
    )

    exit_code = hook_log_extractor.main()

    assert exit_code == 0
    assert captured_arguments["full_rebuild"] is False


def test_run_query_returns_nonzero_for_unknown_query(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = hook_log_extractor.run_query("definitely_not_a_query_name")

    captured = capsys.readouterr()
    assert exit_code == EXIT_CODE_UNKNOWN_QUERY
    assert "Unknown query" in captured.err


def test_run_query_returns_nonzero_for_invalid_query_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = hook_log_extractor.run_query("../../../etc/passwd")

    captured = capsys.readouterr()
    assert exit_code == EXIT_CODE_UNKNOWN_QUERY
    assert "Invalid query name" in captured.err


def test_run_query_rejects_uppercase_and_hyphen_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code_upper = hook_log_extractor.run_query("UPPER_CASE")
    exit_code_hyphen = hook_log_extractor.run_query("has-hyphen")

    captured = capsys.readouterr()
    assert exit_code_upper == EXIT_CODE_UNKNOWN_QUERY
    assert exit_code_hyphen == EXIT_CODE_UNKNOWN_QUERY
    assert captured.err.count("Invalid query name") == 2


def test_save_offsets_cleans_up_temp_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_file = tmp_path / "state.json"

    def _fail_replace(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(hook_log_extractor.os, "replace", _fail_replace)

    with pytest.raises(OSError):
        hook_log_extractor.save_offsets(
            str(state_file),
            {"C:/foo.jsonl": {"byte_offset": 100, "line_number": 2}},
        )

    leftover_temp_files = list(tmp_path.glob("tmp*"))
    assert leftover_temp_files == []


def test_save_offsets_cleans_up_temp_file_when_json_dump_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_file = tmp_path / "state.json"

    def _fail_dump(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("dump failed")

    monkeypatch.setattr(hook_log_extractor.json, "dump", _fail_dump)

    with pytest.raises(ValueError):
        hook_log_extractor.save_offsets(
            str(state_file),
            {"C:/foo.jsonl": {"byte_offset": 100, "line_number": 2}},
        )

    leftover_temp_files = list(tmp_path.glob("tmp*"))
    assert leftover_temp_files == []


def test_load_offsets_propagates_os_error_other_than_missing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")

    def _raise_permission(*_args: Any, **_kwargs: Any) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(hook_log_extractor.io, "open", _raise_permission)

    with pytest.raises(PermissionError):
        hook_log_extractor.load_offsets(str(state_file))


def test_load_offsets_returns_empty_for_malformed_json(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text("not valid json {", encoding="utf-8")

    assert hook_log_extractor.load_offsets(str(state_file)) == {}


def test_iter_attachment_records_accepts_start_line_number(tmp_path: Path) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    first_line = _make_success_line(tool_use_id="toolu_a")
    second_line = _make_success_line(tool_use_id="toolu_b")
    jsonl_file.write_text(first_line + "\n" + second_line + "\n", encoding="utf-8")
    first_line_byte_length = len((first_line + "\n").encode("utf-8"))

    all_parsed_records_with_zero_start = list(
        hook_log_extractor.iter_attachment_records_from_file(
            str(jsonl_file),
            start_offset=first_line_byte_length,
            start_line_number=0,
        ),
    )
    all_parsed_records_with_offset_start = list(
        hook_log_extractor.iter_attachment_records_from_file(
            str(jsonl_file),
            start_offset=first_line_byte_length,
            start_line_number=10,
        ),
    )

    assert len(all_parsed_records_with_offset_start) == 1
    _, zero_start_line_number, _ = all_parsed_records_with_zero_start[0]
    _, offset_start_line_number, _ = all_parsed_records_with_offset_start[0]
    assert offset_start_line_number == zero_start_line_number + 10


def test_load_offsets_migrates_bare_int_legacy_entries_to_empty(
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "state.json"
    legacy_content = json.dumps({"C:/legacy.jsonl": 1234})
    state_file.write_text(legacy_content, encoding="utf-8")
    warning_log = tmp_path / "hook-extractor.log"

    with patch.object(hook_log_extractor, "OFFLINE_WARNING_LOG", str(warning_log)):
        loaded_offsets = hook_log_extractor.load_offsets(str(state_file))

    assert loaded_offsets == {}
    assert warning_log.exists()
    assert "legacy_offsets_format" in warning_log.read_text(encoding="utf-8")


def test_load_offsets_ignores_legacy_warning_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_file = tmp_path / "state.json"
    legacy_content = json.dumps({"C:/legacy.jsonl": 1234})
    state_file.write_text(legacy_content, encoding="utf-8")
    warning_log = tmp_path / "hook-extractor.log"

    real_io_open = hook_log_extractor.io.open

    def _io_open_fails_only_for_warning_log(
        opened_file_path: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if opened_file_path == str(warning_log):
            raise OSError("read-only filesystem")
        return real_io_open(opened_file_path, *args, **kwargs)

    monkeypatch.setattr(
        hook_log_extractor.io, "open", _io_open_fails_only_for_warning_log
    )

    with patch.object(hook_log_extractor, "OFFLINE_WARNING_LOG", str(warning_log)):
        loaded_offsets = hook_log_extractor.load_offsets(str(state_file))

    assert loaded_offsets == {}


def test_save_and_load_offsets_round_trips_new_shape(tmp_path: Path) -> None:
    state_file = tmp_path / "nested" / "state.json"
    original_offset_by_path = {
        "C:/foo.jsonl": {"byte_offset": 100, "line_number": 2},
        "C:/bar.jsonl": {"byte_offset": 250, "line_number": 5},
    }
    hook_log_extractor.save_offsets(str(state_file), original_offset_by_path)
    round_tripped = hook_log_extractor.load_offsets(str(state_file))
    assert round_tripped == original_offset_by_path


def test_run_full_extraction_skips_transcripts_deleted_mid_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")
    state_file = tmp_path / "offsets.json"

    real_exists = hook_log_extractor.os.path.exists

    def _return_false_for_target(each_path: str) -> bool:
        if each_path == str(jsonl_file):
            return False
        return real_exists(each_path)

    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = MagicMock()

    with (
        patch.object(
            hook_log_extractor, "connect_to_neon", return_value=fake_connection
        ),
        patch.object(
            hook_log_extractor.os.path,
            "exists",
            side_effect=_return_false_for_target,
        ),
    ):
        exit_code = hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert exit_code == 0


def test_iter_attachment_records_exposes_final_line_number_after_trailing_non_attachment(
    tmp_path: Path,
) -> None:
    """Final line count must include non-attachment lines after last yield."""
    jsonl_file = tmp_path / "session.jsonl"
    lines = [
        _make_success_line(tool_use_id="toolu_a"),
        json.dumps({"type": "user", "content": "noise"}),
        json.dumps({"type": "assistant", "content": "more noise"}),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    attachment_iterator = hook_log_extractor.iter_attachment_records_from_file(
        str(jsonl_file),
        start_offset=0,
    )
    all_yielded = list(attachment_iterator)

    assert len(all_yielded) == 1
    assert attachment_iterator.final_line_number == 3


def test_run_full_extraction_persists_lines_consumed_with_trailing_noise(
    tmp_path: Path,
) -> None:
    """Resumption must not miscount when non-attachment lines follow the last yield."""
    jsonl_file = tmp_path / "session.jsonl"
    lines = [
        _make_success_line(tool_use_id="toolu_a"),
        json.dumps({"type": "user", "content": "trailing noise"}),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state_file = tmp_path / "offsets.json"

    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    saved_offsets = hook_log_extractor.load_offsets(str(state_file))
    assert saved_offsets[str(jsonl_file)]["line_number"] == 2


def test_iter_attachment_records_final_line_number_when_no_yields(tmp_path: Path) -> None:
    """Final line count reflects lines consumed even when zero records yielded."""
    jsonl_file = tmp_path / "session.jsonl"
    lines = [
        json.dumps({"type": "user", "content": "a"}),
        json.dumps({"type": "assistant", "content": "b"}),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    attachment_iterator = hook_log_extractor.iter_attachment_records_from_file(
        str(jsonl_file),
        start_offset=0,
    )
    all_yielded = list(attachment_iterator)

    assert all_yielded == []
    assert attachment_iterator.final_line_number == 2


def test_iter_attachment_records_exposes_final_byte_offset_after_drain(
    tmp_path: Path,
) -> None:
    """Iterator must report byte position reached after EOF, even with zero yields."""
    jsonl_file = tmp_path / "session.jsonl"
    lines = [
        json.dumps({"type": "user", "content": "a"}),
        json.dumps({"type": "assistant", "content": "b"}),
    ]
    full_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    jsonl_file.write_bytes(full_bytes)

    attachment_iterator = hook_log_extractor.iter_attachment_records_from_file(
        str(jsonl_file),
        start_offset=0,
    )
    list(attachment_iterator)

    assert attachment_iterator.final_byte_offset == len(full_bytes)


def test_run_full_extraction_persists_offset_with_only_non_hook_attachments(
    tmp_path: Path,
) -> None:
    """Offset must advance when iterator drained file yielding zero hook records."""
    jsonl_file = tmp_path / "session.jsonl"
    lines = [
        json.dumps({"type": "user", "content": "noise"}),
        json.dumps({"type": "assistant", "content": "more noise"}),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state_file = tmp_path / "offsets.json"

    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    saved_offsets = hook_log_extractor.load_offsets(str(state_file))
    assert str(jsonl_file) in saved_offsets
    persisted_byte_offset = saved_offsets[str(jsonl_file)]["byte_offset"]
    assert persisted_byte_offset == jsonl_file.stat().st_size


def test_run_full_extraction_persists_final_offset_not_file_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted byte_offset must equal iterator.final_byte_offset.

    Iterator-derived persistence is proven by equality between the
    saved offset and the iterator's ``final_byte_offset`` for a
    transcript that has been read to completion. The iterator's final
    offset matches the known initial byte length, and the persisted
    value matches that same iterator-reported value, so the save path
    sources its number from the iterator rather than from
    ``os.path.getsize`` (which the production code no longer calls).
    """
    jsonl_file = tmp_path / "session.jsonl"
    initial_line_bytes = (_make_success_line() + "\n").encode("utf-8")
    jsonl_file.write_bytes(initial_line_bytes)
    initial_byte_length = len(initial_line_bytes)

    state_file = tmp_path / "offsets.json"

    captured_iterators: list[hook_log_extractor.AttachmentRecordIterator] = []
    real_iterator_factory = hook_log_extractor.iter_attachment_records_from_file

    def _capturing_iterator_factory(
        jsonl_file_path: str,
        start_offset: int,
        start_line_number: int = 0,
    ) -> hook_log_extractor.AttachmentRecordIterator:
        produced_iterator = real_iterator_factory(
            jsonl_file_path,
            start_offset=start_offset,
            start_line_number=start_line_number,
        )
        captured_iterators.append(produced_iterator)
        return produced_iterator

    monkeypatch.setattr(
        hook_log_extractor,
        "iter_attachment_records_from_file",
        _capturing_iterator_factory,
    )

    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    saved_offsets = hook_log_extractor.load_offsets(str(state_file))
    assert captured_iterators, "iterator was never produced"
    iterator_reported_final_offset = captured_iterators[0].final_byte_offset
    assert iterator_reported_final_offset == initial_byte_length
    assert (
        saved_offsets[str(jsonl_file)]["byte_offset"]
        == iterator_reported_final_offset
    )


def test_save_offsets_is_serialized_across_threads(tmp_path: Path) -> None:
    """Locked read-modify-write cycles across threads must not clobber entries."""
    state_file = tmp_path / "offsets.json"
    hook_log_extractor.save_offsets(str(state_file), {})

    def _writer_for_path(writer_path: str) -> None:
        with hook_log_extractor._acquire_offsets_lock(str(state_file)):
            existing_offsets = hook_log_extractor.load_offsets(str(state_file))
            existing_offsets[writer_path] = {"byte_offset": 100, "line_number": 1}
            hook_log_extractor.save_offsets(str(state_file), existing_offsets)

    concurrent_threads = [
        threading.Thread(target=_writer_for_path, args=(f"C:/file_{each_index}.jsonl",))
        for each_index in range(5)
    ]
    for each_thread in concurrent_threads:
        each_thread.start()
    for each_thread in concurrent_threads:
        each_thread.join()

    final_offsets = hook_log_extractor.load_offsets(str(state_file))
    assert len(final_offsets) == 5
    for each_index in range(5):
        assert f"C:/file_{each_index}.jsonl" in final_offsets


def test_run_full_extraction_holds_lock_across_load_and_save(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The extraction cycle must acquire a lock around load→mutate→save."""
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")
    state_file = tmp_path / "offsets.json"

    lock_acquisition_count = {"count": 0}

    real_lock_helper = hook_log_extractor._acquire_offsets_lock

    def _counting_lock_helper(state_file_path: str) -> Any:
        lock_acquisition_count["count"] += 1
        return real_lock_helper(state_file_path)

    monkeypatch.setattr(
        hook_log_extractor, "_acquire_offsets_lock", _counting_lock_helper
    )

    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert lock_acquisition_count["count"] >= 1


def test_lock_file_handle_blocking_reraises_permanent_oserror_quickly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permanent OSErrors (e.g. EBADF) must not be retried — re-raise fast.

    EACCES is the documented contention errno for ``LK_NBLCK`` per the
    Microsoft ``_locking`` spec, so this test uses ``EBADF`` (invalid
    file descriptor) as a genuinely permanent failure that must bubble
    up without consuming the retry budget.
    """
    if hook_log_extractor.msvcrt is None:
        pytest.skip("msvcrt retry loop only exists on Windows runtimes")

    lock_file_handle = (tmp_path / "offsets.json.lock").open("a+", encoding="utf-8")
    try:
        def _raise_permanent_oserror(
            file_descriptor: int,
            mode_flag: int,
            byte_count: int,
        ) -> None:
            raise OSError(errno.EBADF, "invalid file descriptor")

        monkeypatch.setattr(
            hook_log_extractor.msvcrt, "locking", _raise_permanent_oserror
        )

        started_at = time.monotonic()
        with pytest.raises(OSError) as excinfo:
            hook_log_extractor._lock_file_handle_blocking(lock_file_handle)
        elapsed_seconds = time.monotonic() - started_at

        assert excinfo.value.errno == errno.EBADF
        assert elapsed_seconds < 1.0
    finally:
        lock_file_handle.close()


def test_lock_file_handle_blocking_caps_retries_on_contention_errno(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contention-errno must be retried a bounded number of times, then raise.

    With ``LK_NBLCK``, contention surfaces as ``EACCES`` per the
    Microsoft ``_locking`` spec; the retry loop must bound the number
    of attempts to ``LOCK_MAXIMUM_RETRY_COUNT`` and then re-raise.
    """
    if hook_log_extractor.msvcrt is None:
        pytest.skip("msvcrt retry loop only exists on Windows runtimes")

    lock_file_handle = (tmp_path / "offsets.json.lock").open("a+", encoding="utf-8")
    try:
        attempt_count = {"value": 0}

        def _raise_contention_oserror(
            file_descriptor: int,
            mode_flag: int,
            byte_count: int,
        ) -> None:
            attempt_count["value"] += 1
            raise OSError(errno.EACCES, "retries exhausted")

        monkeypatch.setattr(
            hook_log_extractor.msvcrt, "locking", _raise_contention_oserror
        )
        monkeypatch.setattr(hook_log_extractor.time, "sleep", lambda _seconds: None)

        with pytest.raises(OSError) as excinfo:
            hook_log_extractor._lock_file_handle_blocking(lock_file_handle)

        assert excinfo.value.errno == errno.EACCES
        assert (
            attempt_count["value"]
            == hook_log_extractor.LOCK_MAXIMUM_RETRY_COUNT
        )
    finally:
        lock_file_handle.close()


def test_lock_file_handle_blocking_uses_nonblocking_mode_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows branch must call msvcrt.locking with LK_NBLCK, not LK_LOCK.

    LK_LOCK blocks internally for ~10 seconds per attempt per the
    Microsoft _locking spec, which compounded with the retry loop
    produces a worst-case wait of ~303s under sustained contention.
    LK_NBLCK raises OSError(EACCES) immediately, leaving the
    Python-level ``time.sleep`` as the sole pacing mechanism so the
    retry budget stays within its intended ~3s total.
    """
    if hook_log_extractor.msvcrt is None:
        pytest.skip("msvcrt mode-flag check only applies on Windows runtimes")

    lock_file_handle = (tmp_path / "offsets.json.lock").open("a+", encoding="utf-8")
    try:
        observed_mode_flags: list[int] = []

        def _record_mode_flag(
            file_descriptor: int,
            mode_flag: int,
            byte_count: int,
        ) -> None:
            observed_mode_flags.append(mode_flag)

        monkeypatch.setattr(
            hook_log_extractor.msvcrt, "locking", _record_mode_flag
        )

        hook_log_extractor._lock_file_handle_blocking(lock_file_handle)

        assert observed_mode_flags == [hook_log_extractor.msvcrt.LK_NBLCK]
    finally:
        lock_file_handle.close()


def test_run_full_extraction_does_not_hold_lock_across_db_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DB insert must execute while the offsets lock is NOT held."""
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")
    state_file = tmp_path / "offsets.json"

    lock_currently_held = {"value": False}
    lock_held_during_insert = {"value": False}

    real_lock_helper = hook_log_extractor._acquire_offsets_lock

    @contextlib.contextmanager
    def _tracking_lock_helper(passed_state_file_path: str) -> Any:
        lock_currently_held["value"] = True
        try:
            with real_lock_helper(passed_state_file_path):
                yield
        finally:
            lock_currently_held["value"] = False

    def _observe_lock_during_insert(*_args: Any, **_kwargs: Any) -> None:
        if lock_currently_held["value"]:
            lock_held_during_insert["value"] = True

    monkeypatch.setattr(
        hook_log_extractor, "_acquire_offsets_lock", _tracking_lock_helper
    )

    fake_cursor = MagicMock()
    fake_cursor.executemany.side_effect = _observe_lock_during_insert
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        hook_log_extractor, "connect_to_neon", return_value=fake_connection
    ):
        hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    assert fake_cursor.executemany.called, (
        "Test setup failed: DB insert never ran"
    )
    assert not lock_held_during_insert["value"], (
        "Offsets lock must not be held during DB insert calls"
    )


def test_run_full_extraction_preserves_external_offset_updates(
    tmp_path: Path,
) -> None:
    """Narrow-scope save must merge with concurrent writers, not clobber."""
    jsonl_file = tmp_path / "session.jsonl"
    jsonl_file.write_text(_make_success_line() + "\n", encoding="utf-8")
    state_file = tmp_path / "offsets.json"

    fake_cursor = MagicMock()
    fake_connection = MagicMock()
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    other_path_entry = {
        "C:/other_session.jsonl": {"byte_offset": 777, "line_number": 9},
    }

    original_save_offsets = hook_log_extractor.save_offsets

    def _save_then_inject_external_writer(
        passed_state_file_path: str,
        passed_offsets: dict[str, dict[str, int]],
    ) -> None:
        original_save_offsets(passed_state_file_path, passed_offsets)
        if other_path_entry["C:/other_session.jsonl"][
            "byte_offset"
        ] == 777 and "C:/other_session.jsonl" not in passed_offsets:
            loaded_from_disk = hook_log_extractor.load_offsets(passed_state_file_path)
            loaded_from_disk["C:/other_session.jsonl"] = other_path_entry[
                "C:/other_session.jsonl"
            ]
            original_save_offsets(passed_state_file_path, loaded_from_disk)

    with (
        patch.object(
            hook_log_extractor, "connect_to_neon", return_value=fake_connection
        ),
        patch.object(
            hook_log_extractor, "save_offsets", _save_then_inject_external_writer
        ),
    ):
        hook_log_extractor.run_full_extraction(
            transcripts_root=str(tmp_path),
            state_file_path=str(state_file),
            full_rebuild=False,
        )

    final_offsets = hook_log_extractor.load_offsets(str(state_file))
    assert "C:/other_session.jsonl" in final_offsets
    assert final_offsets["C:/other_session.jsonl"] == {
        "byte_offset": 777,
        "line_number": 9,
    }
    assert str(jsonl_file) in final_offsets
