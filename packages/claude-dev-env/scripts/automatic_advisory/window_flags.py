"""Windows creation flags that keep the advisory poller and its children off the screen.

A poller that owns no console makes each git call and each check it starts
open a fresh console window for a moment. A poller that owns a hidden console
passes that hidden console down to every descendant, and nothing appears.
"""

from __future__ import annotations

import subprocess
import sys

from .config.constants import (
    CREATE_NEW_PROCESS_GROUP_ATTRIBUTE,
    CREATE_NO_WINDOW_ATTRIBUTE,
    WINDOWS_PLATFORM,
)


def hidden_window_creation_flags() -> int:
    """Return the flag that runs a Windows child without a visible console.

    Returns:
        The hidden-console flag on Windows, zero elsewhere.
    """
    if sys.platform != WINDOWS_PLATFORM:
        return 0
    return getattr(subprocess, CREATE_NO_WINDOW_ATTRIBUTE, 0)


def detached_poller_creation_flags() -> int:
    """Return the flags for the long-running poller on Windows.

    Returns:
        A new process group plus a hidden console on Windows, zero elsewhere.
    """
    if sys.platform != WINDOWS_PLATFORM:
        return 0
    return getattr(subprocess, CREATE_NEW_PROCESS_GROUP_ATTRIBUTE, 0) | getattr(
        subprocess, CREATE_NO_WINDOW_ATTRIBUTE, 0
    )
