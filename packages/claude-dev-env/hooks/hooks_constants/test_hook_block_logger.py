"""Tests for the shared hook block logger."""

from __future__ import annotations

import datetime
import json
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402


def test_log_hook_block_writes_parseable_json_line(tmp_path: Path) -> None:
    with patch.object(Path, "home", return_value=tmp_path):
        log_hook_block(
            calling_hook_name="test_hook.py",
            hook_event="PreToolUse",
            block_reason="test block reason",
            tool_name="Bash",
            offending_input_preview="echo hello",
        )

    log_path = tmp_path / ".claude" / "logs" / "hook-blocks.log"
    assert log_path.exists()
    line = log_path.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)

    assert "timestamp" in parsed
    assert parsed["hook"] == "test_hook.py"
    assert parsed["event"] == "PreToolUse"
    assert parsed["tool"] == "Bash"
    assert parsed["reason"] == "test block reason"
    assert parsed["preview"] == "echo hello"


def test_log_hook_block_creates_logs_directory(tmp_path: Path) -> None:
    with patch.object(Path, "home", return_value=tmp_path):
        log_hook_block(
            calling_hook_name="some_hook.py",
            hook_event="Stop",
            block_reason="stop reason",
        )

    log_path = tmp_path / ".claude" / "logs" / "hook-blocks.log"
    assert log_path.exists()


def test_log_hook_block_omits_none_fields(tmp_path: Path) -> None:
    with patch.object(Path, "home", return_value=tmp_path):
        log_hook_block(
            calling_hook_name="minimal_hook.py",
            hook_event="PreToolUse",
            block_reason="some reason",
        )

    log_path = tmp_path / ".claude" / "logs" / "hook-blocks.log"
    line = log_path.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert "tool" not in parsed
    assert "preview" not in parsed


def test_log_hook_block_appends_multiple_records(tmp_path: Path) -> None:
    with patch.object(Path, "home", return_value=tmp_path):
        log_hook_block(
            calling_hook_name="hook_a.py",
            hook_event="PreToolUse",
            block_reason="first",
        )
        log_hook_block(
            calling_hook_name="hook_b.py",
            hook_event="Stop",
            block_reason="second",
        )

    log_path = tmp_path / ".claude" / "logs" / "hook-blocks.log"
    all_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(all_lines) == 2
    first_parsed = json.loads(all_lines[0])
    second_parsed = json.loads(all_lines[1])
    assert first_parsed["hook"] == "hook_a.py"
    assert second_parsed["hook"] == "hook_b.py"


def test_log_hook_block_swallows_io_error_on_unwritable_log(tmp_path: Path) -> None:
    logs_dir = tmp_path / ".claude" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "hook-blocks.log"
    log_path.write_text("", encoding="utf-8")
    log_path.chmod(stat.S_IREAD)

    try:
        with patch.object(Path, "home", return_value=tmp_path):
            log_hook_block(
                calling_hook_name="any_hook.py",
                hook_event="PreToolUse",
                block_reason="reason",
            )
    except OSError:
        pytest.fail("log_hook_block raised OSError on unwritable log file")
    finally:
        log_path.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_log_hook_block_swallows_runtime_error_when_home_unresolvable() -> None:
    def raise_home_resolution_failure() -> Path:
        raise RuntimeError("Could not determine home directory.")

    with patch.object(Path, "home", side_effect=raise_home_resolution_failure):
        try:
            returned_nothing = log_hook_block(
                calling_hook_name="any_hook.py",
                hook_event="PreToolUse",
                block_reason="reason",
            )
        except RuntimeError:
            pytest.fail("log_hook_block raised RuntimeError when home was unresolvable")

    assert returned_nothing is None


def test_log_hook_block_truncates_long_preview(tmp_path: Path) -> None:
    long_input = "x" * 600

    with patch.object(Path, "home", return_value=tmp_path):
        log_hook_block(
            calling_hook_name="hook.py",
            hook_event="PreToolUse",
            block_reason="reason",
            offending_input_preview=long_input,
        )

    log_path = tmp_path / ".claude" / "logs" / "hook-blocks.log"
    line = log_path.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert len(parsed["preview"]) <= 500


def test_log_hook_block_timestamp_is_iso8601(tmp_path: Path) -> None:
    before = datetime.datetime.now()
    with patch.object(Path, "home", return_value=tmp_path):
        log_hook_block(
            calling_hook_name="ts_hook.py",
            hook_event="PreToolUse",
            block_reason="ts test",
        )
    after = datetime.datetime.now()

    log_path = tmp_path / ".claude" / "logs" / "hook-blocks.log"
    line = log_path.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    parsed_timestamp = datetime.datetime.fromisoformat(parsed["timestamp"])
    assert before <= parsed_timestamp <= after
