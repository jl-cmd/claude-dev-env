"""Hold a best-effort exclusive lock across one read-modify-write of a state file.

Two hooks can reach the same state file in one turn. The file is written
through a temporary-plus-replace, so it is never torn; what this closes is
the separate lost-update race, where one writer reads before the other
writes and then overwrites it.

::

    with hold_state_file_lock(state_file):
        all_stored = read(state_file)
        write(state_file, updated(all_stored))

The lock is best effort. A caller that cannot take it inside the timeout
proceeds without it rather than stalling the tool call that triggered it.
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    LOCK_ACQUIRE_RETRY_SECONDS,
    LOCK_ACQUIRE_TIMEOUT_SECONDS,
    SESSION_EDIT_LOCK_FILE_SUFFIX,
)


def _acquire_lock_descriptor(lock_file: Path) -> int | None:
    """Grab the exclusive lock, spinning until it frees or the timeout passes.

    Args:
        lock_file: Path to the lock file beside the state file.

    Returns:
        An open descriptor for the held lock, or None when it stayed held
        past the acquire timeout.
    """
    lock_acquire_deadline = time.monotonic() + LOCK_ACQUIRE_TIMEOUT_SECONDS
    while True:
        try:
            return os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= lock_acquire_deadline:
                return None
            time.sleep(LOCK_ACQUIRE_RETRY_SECONDS)


@contextlib.contextmanager
def hold_state_file_lock(state_file: Path) -> Iterator[None]:
    """Hold the lock beside one state file for the body of the with-block.

    Args:
        state_file: The state file whose read-modify-write is being guarded.

    Yields:
        Control to the caller while the lock is held.
    """
    lock_file = state_file.with_name(state_file.name + SESSION_EDIT_LOCK_FILE_SUFFIX)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_descriptor = _acquire_lock_descriptor(lock_file)
    try:
        yield
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
            lock_file.unlink(missing_ok=True)
