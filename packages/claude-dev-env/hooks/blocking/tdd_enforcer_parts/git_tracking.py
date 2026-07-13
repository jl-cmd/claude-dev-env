"""Detect a write that restores a tracked-but-absent production file.

::

    remove orders.py (git-tracked) -> Write orders.py  -> restore (allow)
    Write brand_new.py (untracked, absent)             -> new code (gate)

A full rewrite happens as remove-then-Write, so the file is absent on disk
between the two steps. Restoring committed code is not new production code, so
the gate exempts a Write whose target is absent yet tracked in git.
"""

import subprocess
from pathlib import Path

from tdd_enforcer_parts.config.tdd_enforcer_constants import (
    GIT_EXECUTABLE_NAME,
    GIT_LS_FILES_SUBCOMMAND,
    GIT_LS_FILES_TIMEOUT_SECONDS,
    GIT_PATHSPEC_SEPARATOR,
)


def _git_ls_files_command(file_name: str) -> list[str]:
    return [GIT_EXECUTABLE_NAME, GIT_LS_FILES_SUBCOMMAND, GIT_PATHSPEC_SEPARATOR, file_name]


def _git_tracks_path(path: Path) -> bool:
    parent_directory = path.parent
    if not parent_directory.is_dir():
        return False
    try:
        completed = subprocess.run(
            _git_ls_files_command(path.name),
            cwd=str(parent_directory),
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_LS_FILES_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0 and bool(completed.stdout.strip())


def is_absent_but_tracked(path: Path) -> bool:
    """Return whether a write target is absent on disk yet tracked in git.

    ::

        path missing on disk + git ls-files finds it -> True  (restore)
        path present, or git does not track it       -> False

    Args:
        path: The write target.

    Returns:
        True only when the path does not exist but git tracks it, marking the
        write a restore of committed code rather than new production code.
    """
    if path.exists():
        return False
    return _git_tracks_path(path)
