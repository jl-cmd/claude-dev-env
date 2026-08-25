"""Tests for instructions_loaded_logger observability hook."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).parent / "instructions_loaded_logger.py"


def _run_hook(payload: dict, fake_home: Path) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    child_environment["HOME"] = str(fake_home)
    child_environment["USERPROFILE"] = str(fake_home)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
    )


def test_should_write_record_with_known_payload_fields_to_jsonl_log() -> None:
    with tempfile.TemporaryDirectory() as fake_home_string:
        fake_home = Path(fake_home_string)
        payload = {
            "file_path": "/tmp/CLAUDE.md",
            "load_reason": "session_start",
            "memory_type": "User",
            "trigger_file_path": "/tmp/trigger",
            "parent_file_path": "/tmp/parent",
            "globs": ["**/*.py"],
            "session_id": "abc-123",
        }
        completed = _run_hook(payload, fake_home)
        assert completed.returncode == 0, completed.stderr
        log_path = fake_home / ".claude" / "logs" / "instructions_loaded.jsonl"
        assert log_path.exists()
        record = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert record["file_path"] == "/tmp/CLAUDE.md"
        assert record["load_reason"] == "session_start"
        assert record["session_id"] == "abc-123"
        assert "timestamp" in record


def test_should_exclude_instruction_body_and_unrelated_secret_like_fields(
    tmp_path: Path,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    payload = {
        "file_path": "/tmp/CLAUDE.md",
        "instruction_body": "private instruction text",
        "api_key": "secret-api-key",
        "authorization": "Bearer secret-token",
        "metadata": {
            "instruction_body": "nested private instruction text",
            "api_key": "nested-secret-api-key",
            "authorization": "Nested bearer secret-token",
            "unrelated_secret_like_field": "nested private payload",
        },
    }

    completed = _run_hook(payload, fake_home)

    assert completed.returncode == 0, completed.stderr
    log_path = fake_home / ".claude" / "logs" / "instructions_loaded.jsonl"
    serialized_record = log_path.read_text(encoding="utf-8").strip()
    record = json.loads(serialized_record)
    assert set(record) == {
        "timestamp",
        "file_path",
        "load_reason",
        "memory_type",
        "trigger_file_path",
        "parent_file_path",
        "globs",
        "session_id",
    }
    sensitive_field_names = {
        "instruction_body",
        "api_key",
        "authorization",
        "metadata",
        "unrelated_secret_like_field",
    }
    sensitive_field_values = {
        "private instruction text",
        "secret-api-key",
        "Bearer secret-token",
        "nested private instruction text",
        "nested-secret-api-key",
        "Nested bearer secret-token",
        "nested private payload",
    }
    for each_sensitive_text in sensitive_field_names | sensitive_field_values:
        assert each_sensitive_text not in serialized_record


def test_should_exit_zero_and_record_error_when_stdin_payload_is_invalid_json() -> None:
    with tempfile.TemporaryDirectory() as fake_home_string:
        fake_home = Path(fake_home_string)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input="not json",
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(fake_home), "USERPROFILE": str(fake_home)},
        )
        assert completed.returncode == 0, completed.stderr
        log_path = fake_home / ".claude" / "logs" / "instructions_loaded.jsonl"
        assert log_path.exists()
        record = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert "error" in record
        assert "timestamp" in record


def test_should_exit_zero_when_log_directory_creation_fails() -> None:
    with tempfile.TemporaryDirectory() as fake_home_string:
        fake_home = Path(fake_home_string)
        blocking_file = fake_home / ".claude"
        blocking_file.write_text("not a directory", encoding="utf-8")
        payload = {
            "file_path": "/tmp/CLAUDE.md",
            "load_reason": "path_glob_match",
            "memory_type": "User",
            "trigger_file_path": None,
            "parent_file_path": None,
            "globs": None,
            "session_id": "abc-123",
        }
        completed = _run_hook(payload, fake_home)
        assert completed.returncode == 0, completed.stderr
