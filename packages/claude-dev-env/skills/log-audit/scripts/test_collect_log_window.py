"""Tests for collect_log_window — parsing and windowing hook-block records."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from collect_log_window import (  # noqa: E402
    LogRecord,
    collect_records,
    parse_log_line,
    read_log_window,
)


def _block_line(timestamp_text: str, hook_name: str, reason_text: str) -> str:
    return json.dumps(
        {
            "timestamp": timestamp_text,
            "hook": hook_name,
            "event": "PreToolUse",
            "reason": reason_text,
        }
    )


class TestParseLogLine:
    def test_parses_a_well_formed_block_record(self) -> None:
        line = _block_line(
            "2026-07-03T09:00:00", "plain_language_blocker", "Heavy word"
        )
        record = parse_log_line(line)
        assert record == LogRecord(
            timestamp=datetime(2026, 7, 3, 9, 0, 0),
            source="plain_language_blocker",
            level="block",
            message="Heavy word",
        )

    def test_returns_none_for_a_blank_line(self) -> None:
        assert parse_log_line("   ") is None

    def test_returns_none_for_non_json(self) -> None:
        assert parse_log_line("not json at all") is None

    def test_returns_none_when_reason_is_missing(self) -> None:
        line = json.dumps({"timestamp": "2026-07-03T09:00:00", "hook": "x"})
        assert parse_log_line(line) is None

    def test_returns_none_for_an_unparseable_timestamp(self) -> None:
        line = _block_line("not-a-timestamp", "x", "y")
        assert parse_log_line(line) is None


class TestCollectRecords:
    def test_keeps_only_records_at_or_after_the_window_start(self) -> None:
        window_start = datetime(2026, 7, 3, 8, 0, 0)
        log_text = "\n".join(
            [
                _block_line("2026-07-03T07:59:59", "old_hook", "before window"),
                _block_line("2026-07-03T08:00:00", "edge_hook", "on the boundary"),
                _block_line("2026-07-03T09:30:00", "new_hook", "inside window"),
            ]
        )
        records = collect_records(log_text, window_start)
        assert [each_record.source for each_record in records] == [
            "edge_hook",
            "new_hook",
        ]

    def test_skips_malformed_lines(self) -> None:
        window_start = datetime(2026, 7, 3, 0, 0, 0)
        log_text = "\n".join(
            [
                "garbage",
                _block_line("2026-07-03T09:00:00", "good_hook", "kept"),
                "",
            ]
        )
        records = collect_records(log_text, window_start)
        assert len(records) == 1
        assert records[0].source == "good_hook"


class TestReadLogWindow:
    def test_returns_empty_list_when_the_log_is_absent(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "hook-blocks.log"
        assert read_log_window(missing_path, 24, datetime(2026, 7, 3, 12, 0, 0)) == []

    def test_reads_records_inside_the_window_from_a_real_file(
        self, tmp_path: Path
    ) -> None:
        now = datetime(2026, 7, 3, 12, 0, 0)
        recent_time = (now - timedelta(hours=1)).isoformat()
        stale_time = (now - timedelta(hours=48)).isoformat()
        log_path = tmp_path / "hook-blocks.log"
        log_path.write_text(
            "\n".join(
                [
                    _block_line(stale_time, "stale_hook", "too old"),
                    _block_line(recent_time, "recent_hook", "in window"),
                ]
            ),
            encoding="utf-8",
        )
        records = read_log_window(log_path, 24, now)
        assert [each_record.source for each_record in records] == ["recent_hook"]
