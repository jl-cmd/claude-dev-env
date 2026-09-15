"""Reach the hidden-window helpers from the scripts this directory deploys.

The installer copies this directory into a profile that holds no installed
Python distribution, and this repository's own tests run the deployed scripts
under ``python -S -E``, which hides every installed package from the child
process. On both routes ``hooks_constants`` is reachable only through the
deployed ``hooks`` directory, so this module puts that directory on
``sys.path`` and re-exports the helpers a caller asks for::

    from subprocess_window_access import hidden_window_creation_flags

The directory goes on the end of ``sys.path``. ``PathFinder`` runs ahead of
every editable-install finder, so a trailing entry still selects the deployed
copy, and the head of ``sys.path`` stays exactly as the caller left it. A
caller that prepended its own roots keeps them first.
"""

from __future__ import annotations

import sys
from pathlib import Path

_subprocess_window_hooks_directory = ""
for each_ancestor_directory in Path(__file__).resolve().parents:
    if (each_ancestor_directory / "hooks" / "hooks_constants").is_dir():
        _subprocess_window_hooks_directory = str(each_ancestor_directory / "hooks")
        break
if _subprocess_window_hooks_directory not in sys.path:
    sys.path.append(_subprocess_window_hooks_directory)

from hooks_constants.subprocess_window import (
    HiddenWindowStartupInfo,
    detached_hidden_window_creation_flags,
    hidden_window_creation_flags,
    inherited_stream_startup_info,
)

__all__ = [
    "HiddenWindowStartupInfo",
    "detached_hidden_window_creation_flags",
    "hidden_window_creation_flags",
    "inherited_stream_startup_info",
]
