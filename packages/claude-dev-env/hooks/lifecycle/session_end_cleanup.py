#!/usr/bin/env python3
import json
import os
import sys
import time
from typing import Callable

CACHE_DIR = os.path.expanduser("~/.claude/cache/")
STALE_THRESHOLD_DAYS = 7
BACKUP_RETENTION_DAYS = 30
SECONDS_PER_DAY = 86400


def purge_old_entries(
    directory: str,
    max_age_days: int,
    should_include: Callable[[os.DirEntry[str]], bool] = lambda _entry: True,
) -> None:
    if not os.path.exists(directory):
        return
    cutoff_time = time.time() - (max_age_days * SECONDS_PER_DAY)
    try:
        for each_entry in os.scandir(directory):
            if should_include(each_entry):
                try:
                    if each_entry.stat().st_mtime < cutoff_time:
                        os.unlink(each_entry.path)
                except OSError:
                    pass
    except OSError:
        pass


def main() -> None:
    try:
        json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    purge_old_entries(
        CACHE_DIR,
        STALE_THRESHOLD_DAYS,
        should_include=lambda each_entry: each_entry.name.startswith("claude-ctx-") and each_entry.name.endswith(".json"),
    )
    purge_old_entries(
        CACHE_DIR,
        STALE_THRESHOLD_DAYS,
        should_include=lambda each_entry: each_entry.name.endswith(".tmp"),
    )
    purge_old_entries(
        os.path.join(CACHE_DIR, "transcript-backups"),
        BACKUP_RETENTION_DAYS,
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
