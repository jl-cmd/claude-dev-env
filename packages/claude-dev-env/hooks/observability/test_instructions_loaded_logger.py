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
