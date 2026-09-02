"""Ask git about a candidate path: is it a restore, and does it carry a real edit.

::

    remove orders.py (git-tracked) -> Write orders.py  -> restore (allow)
    Write brand_new.py (untracked, absent)             -> new code (gate)

A full rewrite happens as remove-then-Write, so the file is absent on disk
between the two steps. Restoring committed code is not new production code, so
the gate exempts a Write whose target is absent yet tracked in git.

``has_uncommitted_change_from_head`` answers a second, related question the
content-hash store's first-sight check needs: whether a candidate test file
already carries content HEAD does not have, so a `touch` on an already-clean,
committed test cannot pass as a first sighting.
"""

import subprocess
from pathlib import Path

from tdd_enforcer_parts.config.tdd_enforcer_constants import (
    GIT_DIFF_QUIET_FLAG,
    GIT_DIFF_SUBCOMMAND,
    GIT_DIFF_TIMEOUT_SECONDS,
    GIT_EXECUTABLE_NAME,
    GIT_HEAD_REVISION,
    GIT_LS_FILES_SUBCOMMAND,
    GIT_LS_FILES_TIMEOUT_SECONDS,
    GIT_PATHSPEC_SEPARATOR,
)


def _git_ls_files_command(file_name: str) -> list[str]:
    return [GIT_EXECUTABLE_NAME, GIT_LS_FILES_SUBCOMMAND, GIT_PATHSPEC_SEPARATOR, file_name]


def _git_diff_quiet_against_head_command(file_name: str) -> list[str]:
    return [
        GIT_EXECUTABLE_NAME,
        GIT_DIFF_SUBCOMMAND,
        GIT_DIFF_QUIET_FLAG,
        GIT_HEAD_REVISION,
        GIT_PATHSPEC_SEPARATOR,
        file_name,
    ]


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


def _working_tree_differs_from_head(path: Path) -> bool:
    """Compare the working tree to HEAD, not to the index.

    A plain ``git diff`` (no revision argument) compares the working tree to
    the index, so a file that was just ``git add``-ed reads as unchanged even
    when it holds content HEAD never had. Naming ``HEAD`` folds the index and
    the working tree into one comparison against the last commit, catching a
    staged-but-uncommitted new file and a staged edit alike.
    """
    try:
        completed = subprocess.run(
            _git_diff_quiet_against_head_command(path.name),
            cwd=str(path.parent),
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_DIFF_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    return completed.returncode != 0


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


def has_uncommitted_change_from_head(path: Path) -> bool:
    """Return whether *path* carries content its git HEAD does not have.

    ::

        untracked file                -> True  (no HEAD entry to match)
        tracked, working tree != HEAD -> True  (a real edit this session)
        tracked, working tree == HEAD -> False (clean; a touch cannot pass)
        git unavailable or errors     -> True  (cannot prove it is clean)

    Args:
        path: The candidate test file to check.

    Returns:
        True unless git can positively confirm the file is tracked and its
        working-tree content matches HEAD exactly.
    """
    if not _git_tracks_path(path):
        return True
    return _working_tree_differs_from_head(path)
