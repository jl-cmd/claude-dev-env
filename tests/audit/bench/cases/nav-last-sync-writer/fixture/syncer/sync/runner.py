from pathlib import Path

from syncer.feed.client import fetch_since
from syncer.sync.state import read_cursor, record_completion


def run_once(state_path: Path) -> int:
    all_records, next_cursor = fetch_since(read_cursor(state_path))
    record_completion(state_path, next_cursor)
    return len(all_records)
