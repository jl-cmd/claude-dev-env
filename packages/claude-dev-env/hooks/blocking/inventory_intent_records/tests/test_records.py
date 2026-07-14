"""Tests for the shared inventory/orphan pending-intent records."""

import tempfile
import time
from pathlib import Path

import pytest
from inventory_intent_records import records
from inventory_intent_records.config.intent_records_constants import (
    INTENT_FRESHNESS_WINDOW_SECONDS,
)

SESSION_ID = "session-abc"
DIRECTORY = "/tmp/package_directory"
FILENAME = "new_module.py"
OTHER_FILENAME = "other_module.py"


@pytest.fixture(autouse=True)
def _isolated_temp_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the records file at an isolated temp directory for each test."""
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))


def test_recorded_file_intent_is_found_fresh() -> None:
    records.record_file_intent(SESSION_ID, DIRECTORY, FILENAME)
    assert records.has_fresh_file_intent(SESSION_ID, DIRECTORY, FILENAME) is True


def test_recorded_row_intent_is_found_fresh() -> None:
    records.record_row_intent(SESSION_ID, DIRECTORY, FILENAME)
    assert records.has_fresh_row_intent(SESSION_ID, DIRECTORY, FILENAME) is True


def test_file_intent_does_not_match_a_different_filename() -> None:
    records.record_file_intent(SESSION_ID, DIRECTORY, FILENAME)
    assert records.has_fresh_file_intent(SESSION_ID, DIRECTORY, OTHER_FILENAME) is False


def test_file_and_row_intents_do_not_cross_match() -> None:
    records.record_file_intent(SESSION_ID, DIRECTORY, FILENAME)
    assert records.has_fresh_row_intent(SESSION_ID, DIRECTORY, FILENAME) is False


def test_consume_file_intent_removes_it() -> None:
    records.record_file_intent(SESSION_ID, DIRECTORY, FILENAME)
    records.consume_file_intent(SESSION_ID, DIRECTORY, FILENAME)
    assert records.has_fresh_file_intent(SESSION_ID, DIRECTORY, FILENAME) is False


def test_consume_row_intent_removes_it() -> None:
    records.record_row_intent(SESSION_ID, DIRECTORY, FILENAME)
    records.consume_row_intent(SESSION_ID, DIRECTORY, FILENAME)
    assert records.has_fresh_row_intent(SESSION_ID, DIRECTORY, FILENAME) is False


def test_stale_intent_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    expired_time = time.time() - INTENT_FRESHNESS_WINDOW_SECONDS - 1.0
    monkeypatch.setattr(records.time, "time", lambda: expired_time)
    records.record_file_intent(SESSION_ID, DIRECTORY, FILENAME)
    monkeypatch.undo()
    assert records.has_fresh_file_intent(SESSION_ID, DIRECTORY, FILENAME) is False


def test_missing_records_file_reads_as_no_intent() -> None:
    assert records.has_fresh_file_intent("never-recorded", DIRECTORY, FILENAME) is False
    assert records.has_fresh_row_intent("never-recorded", DIRECTORY, FILENAME) is False


def test_corrupt_records_file_reads_as_no_intent(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "claude-inventory-intent-session-abc.json"
    corrupt_file.write_text("{not valid json", encoding="utf-8")
    assert records.has_fresh_file_intent(SESSION_ID, DIRECTORY, FILENAME) is False


def test_non_utf8_records_file_reads_as_no_intent(tmp_path: Path) -> None:
    byte_corrupt_file = tmp_path / "claude-inventory-intent-session-abc.json"
    byte_corrupt_file.write_bytes(b"\xff\xfe not valid utf-8")
    assert records.has_fresh_file_intent(SESSION_ID, DIRECTORY, FILENAME) is False
    assert records.has_fresh_row_intent(SESSION_ID, DIRECTORY, FILENAME) is False
