#!/usr/bin/env python3
"""End a spawned process and every descendant it started.

A CLI launched from a script often spawns its own children, and those
grandchildren hold the capture pipe open. Killing the direct child alone leaves
them running and the reading caller waiting on a pipe that never reaches
end-of-file. This module ends the whole tree instead::

    terminate_process_tree(process)   ok:   grandchildren die, pipes close
    process.kill()                    flag: grandchildren outlive the parent

Windows tears the tree down with ``taskkill /T``. POSIX signals the child's
process group. The group signal reaches only the intended tree when the child
leads its own session, so every caller pairs the two calls::

    process = subprocess.Popen(
        argv, start_new_session=should_start_new_session()
    )
    terminate_process_tree(process)
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

_config_directory = str(Path(__file__).resolve().parent / "config")
if _config_directory not in sys.path:
    sys.path.insert(0, _config_directory)

from process_tree_scripts_constants.process_tree_kill_constants import (  # noqa: E402
    PROCESS_TREE_KILL_TIMEOUT_SECONDS,
    WINDOWS_TASKKILL_COMMAND,
    WINDOWS_TASKKILL_FORCE_FLAG,
    WINDOWS_TASKKILL_PID_FLAG,
    WINDOWS_TASKKILL_TREE_FLAG,
)

process_tree_subprocess_run = subprocess.run


def should_start_new_session() -> bool:
    """Report whether a child should be launched as its own session leader.

    POSIX ends a tree through ``os.killpg``, which signals every process in the
    group. A child sharing the caller's group would take the caller down with
    it, so the child leads a session of its own. Windows has no session flag
    and ends the tree by process id, so the answer there is False.
    """
    return sys.platform != "win32"


def _kill_windows_process_tree(process_identifier: int) -> None:
    """End a Windows process and every descendant it started, by process id.

    Swallows taskkill failures so the caller still falls back to
    ``Popen.kill()`` and its own drain. A raised ``TimeoutExpired`` here would
    replace the caller's original timeout exception and skip that fallback.
    """
    try:
        process_tree_subprocess_run(
            [
                WINDOWS_TASKKILL_COMMAND,
                WINDOWS_TASKKILL_TREE_FLAG,
                WINDOWS_TASKKILL_FORCE_FLAG,
                WINDOWS_TASKKILL_PID_FLAG,
                str(process_identifier),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=PROCESS_TREE_KILL_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return


def _kill_posix_process_group(process_identifier: int) -> None:
    """End a POSIX process group so no grandchild keeps the capture pipe open.

    A process id that is already reaped, or one the caller may not signal,
    raises ``OSError``; this swallows it and returns, so the caller falls back
    to ``Popen.kill()``.

    The leading literal ``sys.platform`` comparison is what lets mypy read the
    rest of the body as POSIX-only. Under a named constant, ``os.getpgid``,
    ``os.killpg``, and ``signal.SIGKILL`` fail type checking on Windows.
    """
    if sys.platform == "win32":
        return
    try:
        process_group_identifier = os.getpgid(process_identifier)
        os.killpg(process_group_identifier, signal.SIGKILL)
    except OSError:
        return


def kill_process_tree_by_identifier(process_identifier: int) -> None:
    """Issue the platform's tree kill for one process id, with no liveness check.

    The platform test is written as a literal ``sys.platform`` comparison
    because that is the form mypy narrows: under a named constant the
    process-group calls in the POSIX branch fail type checking on Windows.

    Args:
        process_identifier: The process id whose tree is ended.
    """
    if sys.platform == "win32":
        _kill_windows_process_tree(process_identifier)
        return
    _kill_posix_process_group(process_identifier)


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """End a running process and every descendant it spawned.

    ::

        already exited             ok:  returns, nothing killed
        tree kill takes            ok:  grandchildren die, pipes close
        tree kill misses the child ok:  Popen.kill() ends the direct child
        child exits mid-kill       ok:  the raised lookup error is swallowed

    Falls back to ``Popen.kill()`` when the direct child survives the tree kill,
    so the caller never waits on a live process.

    Args:
        process: The process whose tree is ended.
    """
    if process.poll() is not None:
        return
    kill_process_tree_by_identifier(process.pid)
    if process.poll() is not None:
        return
    try:
        process.kill()
    except ProcessLookupError:
        return
