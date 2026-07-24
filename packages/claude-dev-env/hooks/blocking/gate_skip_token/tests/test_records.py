"""Tests for the per-session gate-skip-token store."""

import tempfile
import time
from pathlib import Path

import pytest
from gate_skip_token import records
from gate_skip_token.config.gate_skip_token_constants import (
    DEFAULT_PERMISSION_MODE,
    GATE_SKIP_TOKEN_FILE_PREFIX,
    GATE_SKIP_TOKEN_FILE_SUFFIX,
    GATE_SKIP_TOKEN_FRESHNESS_WINDOW_SECONDS,
)

SESSION_ID = "session-abc"
OTHER_SESSION_ID = "session-xyz"
FILE_PATH = "/home/project/module.py"
PROPOSED_CONTENT = "def stays_clean() -> None:\n    return None\n"
DIFFERENT_CONTENT = "def stays_clean() -> None:\n    return True\n"
NON_DEFAULT_PERMISSION_MODE = "acceptEdits"
STALE_MARGIN_SECONDS = 1.0


@pytest.fixture(autouse=True)
def _isolated_temp_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the token file at an isolated temp directory for each test."""
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))


def test_recorded_token_is_honored_once() -> None:
    content_hash = records.content_sha256(PROPOSED_CONTENT)
    records.record_skip_token(SESSION_ID, FILE_PATH, content_hash)
    assert records.has_valid_skip_token(SESSION_ID, FILE_PATH, content_hash) is True


def test_token_past_freshness_window_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    content_hash = records.content_sha256(PROPOSED_CONTENT)
    expired_time = time.time() - GATE_SKIP_TOKEN_FRESHNESS_WINDOW_SECONDS - STALE_MARGIN_SECONDS
    monkeypatch.setattr(records.time, "time", lambda: expired_time)
    records.record_skip_token(SESSION_ID, FILE_PATH, content_hash)
    monkeypatch.undo()
    assert records.has_valid_skip_token(SESSION_ID, FILE_PATH, content_hash) is False


def test_foreign_session_token_is_rejected() -> None:
    content_hash = records.content_sha256(PROPOSED_CONTENT)
    records.record_skip_token(SESSION_ID, FILE_PATH, content_hash)
    assert records.has_valid_skip_token(OTHER_SESSION_ID, FILE_PATH, content_hash) is False


def test_content_hash_mismatch_is_rejected() -> None:
    recorded_hash = records.content_sha256(PROPOSED_CONTENT)
    different_hash = records.content_sha256(DIFFERENT_CONTENT)
    records.record_skip_token(SESSION_ID, FILE_PATH, recorded_hash)
    assert records.has_valid_skip_token(SESSION_ID, FILE_PATH, different_hash) is False


def test_consumed_token_is_not_valid_again() -> None:
    content_hash = records.content_sha256(PROPOSED_CONTENT)
    records.record_skip_token(SESSION_ID, FILE_PATH, content_hash)
    records.consume_skip_token(SESSION_ID, FILE_PATH, content_hash)
    assert records.has_valid_skip_token(SESSION_ID, FILE_PATH, content_hash) is False


def test_corrupt_store_reads_as_no_tokens(tmp_path: Path) -> None:
    token_file = (
        tmp_path / f"{GATE_SKIP_TOKEN_FILE_PREFIX}{SESSION_ID}{GATE_SKIP_TOKEN_FILE_SUFFIX}"
    )
    token_file.write_text("{not valid json", encoding="utf-8")
    content_hash = records.content_sha256(PROPOSED_CONTENT)
    assert records.has_valid_skip_token(SESSION_ID, FILE_PATH, content_hash) is False


def test_should_downgrade_to_ask_only_when_default_and_subset_and_token() -> None:
    assert records.should_downgrade_to_ask(DEFAULT_PERMISSION_MODE, True, True) is True
    assert records.should_downgrade_to_ask(DEFAULT_PERMISSION_MODE, True, False) is False
    assert records.should_downgrade_to_ask(DEFAULT_PERMISSION_MODE, False, True) is False
    assert records.should_downgrade_to_ask(DEFAULT_PERMISSION_MODE, False, False) is False
    assert records.should_downgrade_to_ask(NON_DEFAULT_PERMISSION_MODE, True, True) is False
    assert records.should_downgrade_to_ask(NON_DEFAULT_PERMISSION_MODE, True, False) is False
    assert records.should_downgrade_to_ask(NON_DEFAULT_PERMISSION_MODE, False, True) is False
    assert records.should_downgrade_to_ask(NON_DEFAULT_PERMISSION_MODE, False, False) is False
