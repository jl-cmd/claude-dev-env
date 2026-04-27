#!/usr/bin/env python3
"""Stop-hook wrapper for hook_log_extractor: debounced, fire-and-forget.

Runs after every assistant turn (Stop hook), so per-turn latency must
stay near zero. The wrapper:

1. Reads the last-spawn timestamp; if it falls within the debounce
   window, exits 0 immediately without spawning anything (typical fast
   path: a small file read, well under 10ms).
2. Otherwise records the current timestamp, then launches the extractor
   as a fully detached background process (no stdio, separate process
   group on POSIX or DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP on
   Windows) and returns without waiting for it.

Bitwarden injection: when both ``bws`` is on PATH and
``BWS_ACCESS_TOKEN`` is set, the extractor is launched via
``bws run --`` so the Neon URL never hits disk; otherwise it is
launched directly. The extractor itself exits 0 when
``NEON_HOOK_LOGS_DATABASE_URL`` is unset, so missing dependencies
cannot block session shutdown.

This wrapper always exits 0 so the Stop hook never surfaces a failure.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.hook_log_extractor_constants import (
    BWS_ACCESS_TOKEN_ENV_VAR,
    BWS_EXECUTABLE_NAME,
    BWS_RUN_SEPARATOR,
    BWS_RUN_SUBCOMMAND,
    EXIT_CODE_SUCCESS,
    FLAG_INCREMENTAL,
    STOP_WRAPPER_DEBOUNCE_SECONDS,
    STOP_WRAPPER_EXTRACTOR_SCRIPT_NAME,
    STOP_WRAPPER_LAST_RUN_TIMESTAMP_FILE,
    WINDOWS_CREATE_NEW_PROCESS_GROUP_FLAG,
    WINDOWS_DETACHED_PROCESS_FLAG,
    WINDOWS_OS_NAME,
)


def _extractor_script_path() -> str:
    return str(
        Path(__file__).resolve().parent / STOP_WRAPPER_EXTRACTOR_SCRIPT_NAME
    )


def _last_run_timestamp_path() -> Path:
    return Path(STOP_WRAPPER_LAST_RUN_TIMESTAMP_FILE)


def _is_within_debounce_window() -> bool:
    timestamp_path = _last_run_timestamp_path()
    if not timestamp_path.exists():
        return False
    try:
        previous_timestamp = float(timestamp_path.read_text().strip())
    except (OSError, ValueError):
        return False
    seconds_since_previous_spawn = time.time() - previous_timestamp
    return seconds_since_previous_spawn < STOP_WRAPPER_DEBOUNCE_SECONDS


def _record_current_timestamp() -> None:
    timestamp_path = _last_run_timestamp_path()
    timestamp_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp_path.write_text(str(time.time()))


def _can_use_bws() -> bool:
    if not os.environ.get(BWS_ACCESS_TOKEN_ENV_VAR):
        return False
    return shutil.which(BWS_EXECUTABLE_NAME) is not None


def _detached_spawn_keyword_arguments() -> dict[str, object]:
    spawn_arguments: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == WINDOWS_OS_NAME:
        spawn_arguments["creationflags"] = (
            WINDOWS_DETACHED_PROCESS_FLAG
            | WINDOWS_CREATE_NEW_PROCESS_GROUP_FLAG
        )
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup_info.wShowWindow = subprocess.SW_HIDE
        spawn_arguments["startupinfo"] = startup_info
    else:
        spawn_arguments["start_new_session"] = True
    return spawn_arguments


def _spawn_with_bws() -> None:
    subprocess.Popen(
        [
            BWS_EXECUTABLE_NAME,
            BWS_RUN_SUBCOMMAND,
            BWS_RUN_SEPARATOR,
            sys.executable,
            _extractor_script_path(),
            FLAG_INCREMENTAL,
        ],
        **_detached_spawn_keyword_arguments(),
    )


def _spawn_without_bws() -> None:
    subprocess.Popen(
        [
            sys.executable,
            _extractor_script_path(),
            FLAG_INCREMENTAL,
        ],
        **_detached_spawn_keyword_arguments(),
    )


def main() -> int:
    """Debounce, then fire-and-forget the extractor; always exit 0."""
    try:
        if _is_within_debounce_window():
            return EXIT_CODE_SUCCESS
        _record_current_timestamp()
        if _can_use_bws():
            _spawn_with_bws()
        else:
            _spawn_without_bws()
    except Exception:
        pass
    return EXIT_CODE_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
