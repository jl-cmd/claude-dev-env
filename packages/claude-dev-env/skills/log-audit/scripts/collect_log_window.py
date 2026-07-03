"""Read the recent window of the hook block log into structured records.

Tails the JSON-lines hook block log every blocking hook appends to, and hands
back the block events inside a time window as plain records. Picture the audit
agent waking up: it asks this script for the last few hours of blocks, and gets
one record per block carrying when it happened, which hook fired, and why. Those
records feed cluster_recurrences, which groups them by a normalized signature.

Usage:
    collect_log_window.py --hours 24
    collect_log_window.py --hours 6 --log-path /path/to/hook-blocks.log
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from log_audit_constants.collect_log_window_constants import (  # noqa: E402
    BLOCK_LEVEL_LABEL,
    DEFAULT_WINDOW_HOURS,
    HOOK_BLOCKS_LOG_RELATIVE_PATH,
    LOG_HOOK_KEY,
    LOG_REASON_KEY,
    LOG_TIMESTAMP_KEY,
    RECORD_LEVEL_KEY,
    RECORD_MESSAGE_KEY,
    RECORD_SOURCE_KEY,
    RECORD_TIMESTAMP_KEY,
)


@dataclass(frozen=True)
class LogRecord:
    """One block event read from the hook block log.

    Attributes:
        timestamp: When the block happened, parsed from the record's ISO string.
        source: The hook that blocked, taken from the record's hook field.
        level: The severity label; every hook-block record reads as a block.
        message: The human-readable block reason.
    """

    timestamp: datetime
    source: str
    level: str
    message: str


def parse_log_line(raw_line: str) -> LogRecord | None:
    """Parse one hook-block-log line into a LogRecord.

    Args:
        raw_line: A single line of the JSON-lines hook block log.

    Returns:
        The parsed record, or None when the line is blank, is not a JSON object,
        or omits the timestamp, hook, or reason field, or carries a timestamp
        that does not parse as an ISO datetime.
    """
    stripped_line = raw_line.strip()
    if not stripped_line:
        return None
    try:
        record_fields = json.loads(stripped_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(record_fields, dict):
        return None
    timestamp_text = record_fields.get(LOG_TIMESTAMP_KEY)
    source_text = record_fields.get(LOG_HOOK_KEY)
    message_text = record_fields.get(LOG_REASON_KEY)
    if not isinstance(timestamp_text, str):
        return None
    if not isinstance(source_text, str) or not isinstance(message_text, str):
        return None
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp_text)
    except ValueError:
        return None
    return LogRecord(
        timestamp=parsed_timestamp,
        source=source_text,
        level=BLOCK_LEVEL_LABEL,
        message=message_text,
    )


def _records_within_window(
    all_lines: Iterable[str], window_start: datetime
) -> list[LogRecord]:
    """Parse each line and keep the records at or after the window start.

    Args:
        all_lines: The hook-block-log lines to parse, in file order.
        window_start: The earliest timestamp a kept record may carry.

    Returns:
        The in-window records in the order their lines appear.
    """
    kept_records: list[LogRecord] = []
    for each_line in all_lines:
        parsed_record = parse_log_line(each_line)
        if parsed_record is None:
            continue
        if parsed_record.timestamp >= window_start:
            kept_records.append(parsed_record)
    return kept_records


def collect_records(log_text: str, window_start: datetime) -> list[LogRecord]:
    """Parse log text and keep records at or after the window start.

    Args:
        log_text: The full text of the hook block log.
        window_start: The earliest timestamp a kept record may carry.

    Returns:
        The in-window records in the order they appear in the log.
    """
    return _records_within_window(log_text.splitlines(), window_start)


def read_log_window(
    log_path: Path, window_hours: int, now: datetime
) -> list[LogRecord]:
    """Read the hook block log and return records within the window.

    Args:
        log_path: Path to the JSON-lines hook block log.
        window_hours: How many hours back from now to keep.
        now: The current time the window is measured back from.

    Returns:
        The in-window records, or an empty list when the log file is absent.
    """
    window_start = now - timedelta(hours=window_hours)
    try:
        with log_path.open(encoding="utf-8") as log_file:
            return _records_within_window(log_file, window_start)
    except FileNotFoundError:
        return []


def _default_log_path() -> Path:
    """Return the home-relative path of the hook block log."""
    return Path.home() / HOOK_BLOCKS_LOG_RELATIVE_PATH


def _record_as_json_dict(record: LogRecord) -> dict[str, str]:
    """Render a record as a JSON-ready dict with an ISO timestamp string.

    Args:
        record: The record to render.

    Returns:
        A dict of string values keyed by the record's field names.
    """
    return {
        RECORD_TIMESTAMP_KEY: record.timestamp.isoformat(),
        RECORD_SOURCE_KEY: record.source,
        RECORD_LEVEL_KEY: record.level,
        RECORD_MESSAGE_KEY: record.message,
    }


def main() -> int:
    """Print the recent hook-block records as JSON to stdout.

    Returns:
        The process exit code; zero on success.
    """
    parser = argparse.ArgumentParser(description="Tail the hook block log window.")
    parser.add_argument("--hours", type=int, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument("--log-path", type=str, default=None)
    parsed_arguments = parser.parse_args()
    log_path = (
        Path(parsed_arguments.log_path)
        if parsed_arguments.log_path is not None
        else _default_log_path()
    )
    records = read_log_window(log_path, parsed_arguments.hours, datetime.now())
    json.dump(
        [_record_as_json_dict(each_record) for each_record in records], sys.stdout
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
