"""Named constants for ``process_tree_kill.py``.

Every caller that ends a child process and its descendants reads the taskkill
command, its flags, and the bound on the kill command from here rather than
embedding the values in its own module.
"""

from __future__ import annotations

WINDOWS_TASKKILL_COMMAND: str = "taskkill"
"""Windows command that ends a process by id."""

WINDOWS_TASKKILL_TREE_FLAG: str = "/T"
"""``taskkill`` flag that extends the kill to every descendant process."""

WINDOWS_TASKKILL_FORCE_FLAG: str = "/F"
"""``taskkill`` flag that forces termination rather than requesting it."""

WINDOWS_TASKKILL_PID_FLAG: str = "/PID"
"""``taskkill`` flag that names the target process id."""

PROCESS_TREE_KILL_TIMEOUT_SECONDS: int = 10
"""Seconds allowed for the tree-kill command itself before it is abandoned.

Gates the kill command alone. Each caller sets its own bound on the drain that
follows the kill.
"""
