#!/usr/bin/env python3
"""Stop-hook wrapper for hook_log_extractor that never surfaces a hook failure.

Invokes ``hook_log_extractor.py --incremental`` via ``bws run`` only when
both ``bws`` is on PATH and ``BWS_ACCESS_TOKEN`` is set; otherwise falls
through to run the extractor directly. The extractor itself exits 0 when
``NEON_HOOK_LOGS_DATABASE_URL`` is unset, so the wrapper can rely on that
offline-graceful path. This wrapper always exits 0 so the Stop hook
never blocks session end on a missing dependency.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
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
    STOP_WRAPPER_EXTRACTOR_SCRIPT_NAME,
)


def _extractor_script_path() -> str:
    return str(
        Path(__file__).resolve().parent / STOP_WRAPPER_EXTRACTOR_SCRIPT_NAME
    )


def _can_use_bws() -> bool:
    if not os.environ.get(BWS_ACCESS_TOKEN_ENV_VAR):
        return False
    return shutil.which(BWS_EXECUTABLE_NAME) is not None


def _run_with_bws() -> None:
    subprocess.run(
        [
            BWS_EXECUTABLE_NAME,
            BWS_RUN_SUBCOMMAND,
            BWS_RUN_SEPARATOR,
            sys.executable,
            _extractor_script_path(),
            FLAG_INCREMENTAL,
        ],
        check=False,
    )


def _run_without_bws() -> None:
    subprocess.run(
        [
            sys.executable,
            _extractor_script_path(),
            FLAG_INCREMENTAL,
        ],
        check=False,
    )


def main() -> int:
    """Invoke the extractor with or without bws; swallow all failures."""
    try:
        if _can_use_bws():
            _run_with_bws()
        else:
            _run_without_bws()
    except Exception:
        pass
    return EXIT_CODE_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
