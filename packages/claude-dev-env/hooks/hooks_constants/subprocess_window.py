"""Creation flags that keep a spawned child off the operator's screen on Windows.

A hook or script often runs with no console of its own. When such a process
starts a child on Windows, the operating system gives that child a brand new
console, and the operator sees a black window flash open and shut while agents
work. ``CREATE_NO_WINDOW`` tells Windows to skip that console. Every child this
package spawns passes the flag, so the desktop stays quiet::

    subprocess.run(
        ["git", "status"],
        creationflags=hidden_window_creation_flags(),
    )

On Windows that call returns ``0x08000000`` and no window appears. On Linux and
macOS it returns ``0``, which is the value ``subprocess`` already uses when a
caller passes no ``creationflags`` at all, so behaviour there is unchanged.
``CREATE_NO_WINDOW`` is absent from a non-Windows Python build, so the lookup
reads the attribute at call time and falls back to ``0``.

``CREATE_NO_WINDOW`` gives the child a console of its own. A child that writes
to a stream the caller redirected is unaffected, because the redirected handle
travels with it. A child that inherits the caller's terminal instead loses that
terminal, and the operator stops seeing its output. A few call sites hand their
streams straight to the operator, and those pass
``startupinfo=inherited_stream_startup_info()`` instead. That startup record
keeps the inherited streams and hides the console window, so the operator still
reads the output and still sees no window.

``subprocess.STARTUPINFO`` is a Windows-only name. Typeshed declares it under a
``sys.platform == "win32"`` guard, so a type check that runs on Linux, as this
repository's continuous integration does, cannot see the name at all. The
startup record is therefore described here as a structural ``Protocol`` naming
the two fields this module sets, and the record itself is fetched through
``getattr`` at call time. Both moves match what the module already does for the
creation flags, and they keep the runtime ``sys.platform`` test in one place, so
one function serves every platform.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Protocol

from hooks_constants.subprocess_window_constants import (
    CREATE_NEW_PROCESS_GROUP_ATTRIBUTE,
    CREATE_NO_WINDOW_ATTRIBUTE,
    HIDE_WINDOW_COMMAND_ATTRIBUTE,
    NO_CREATION_FLAGS,
    SHOW_WINDOW_FLAG_ATTRIBUTE,
    STARTUP_INFO_ATTRIBUTE,
    WINDOWS_PLATFORM,
)

__all__ = [
    "HiddenWindowStartupInfo",
    "detached_hidden_window_creation_flags",
    "hidden_window_creation_flags",
    "inherited_stream_startup_info",
]


class HiddenWindowStartupInfo(Protocol):
    """The two ``subprocess.STARTUPINFO`` fields that hide a child's console."""

    dwFlags: int
    wShowWindow: int


def _windows_flag(flag_attribute_name: str) -> int:
    """Return one Windows creation flag, or zero on any other platform.

    Args:
        flag_attribute_name: The name of a ``subprocess`` creation-flag constant.

    Returns:
        The flag value on Windows, and zero elsewhere or when the running
        Python build does not define that constant.
    """
    if sys.platform != WINDOWS_PLATFORM:
        return NO_CREATION_FLAGS
    return int(getattr(subprocess, flag_attribute_name, NO_CREATION_FLAGS))


def hidden_window_creation_flags() -> int:
    """Return the creation flags that start a child without a console window.

    Pass the result as the ``creationflags`` argument of ``subprocess.run``,
    ``subprocess.Popen``, ``subprocess.check_output``, or ``subprocess.call``::

        subprocess.run(["git", "rev-parse", "HEAD"],
                       creationflags=hidden_window_creation_flags())

    Returns:
        The hidden-console flag on Windows, and zero on every other platform.
    """
    return _windows_flag(CREATE_NO_WINDOW_ATTRIBUTE)


def detached_hidden_window_creation_flags() -> int:
    """Return the creation flags for a long-lived child that outlives its parent.

    A detached poller needs its own process group so a console interrupt aimed
    at the parent never reaches it, and it needs the hidden console for the same
    reason every other child does::

        subprocess.Popen(argv,
                         creationflags=detached_hidden_window_creation_flags())

    Returns:
        A new process group combined with the hidden-console flag on Windows,
        and zero on every other platform.
    """
    return _windows_flag(CREATE_NEW_PROCESS_GROUP_ATTRIBUTE) | hidden_window_creation_flags()


def inherited_stream_startup_info() -> HiddenWindowStartupInfo | None:
    """Return a startup record that hides the console of a stream-inheriting child.

    Use this at a call site that lets the child write straight to the operator's
    terminal, where ``hidden_window_creation_flags`` would take that terminal
    away::

        subprocess.run(["python", "-m", "pytest"],
                       startupinfo=inherited_stream_startup_info())

    Returns:
        A Windows startup record asking for a hidden window, and ``None`` on
        every other platform, which is the value ``subprocess`` already uses
        when a caller passes no ``startupinfo`` at all.
    """
    if sys.platform != WINDOWS_PLATFORM:
        return None
    startup_information = getattr(subprocess, STARTUP_INFO_ATTRIBUTE)()
    startup_information.dwFlags |= getattr(
        subprocess, SHOW_WINDOW_FLAG_ATTRIBUTE, NO_CREATION_FLAGS
    )
    startup_information.wShowWindow = getattr(
        subprocess, HIDE_WINDOW_COMMAND_ATTRIBUTE, NO_CREATION_FLAGS
    )
    return startup_information
