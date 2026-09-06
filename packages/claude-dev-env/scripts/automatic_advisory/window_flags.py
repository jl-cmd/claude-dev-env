"""Windows creation flags that hide the advisory poller and its children.

A poller with no console makes each git call and each check open a fresh
console window. A hidden console is inherited by descendants, so those
children stay off the screen.
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
