"""Clear a stale local ``core.hooksPath`` that git seeds into a fresh worktree.

::

    fresh worktree local config:  core.hooksPath = <repo>/.git/hooks
                                                    ^ shadows the global setting
    global config:                core.hooksPath = <path>/.claude/hooks
    after self-heal:              local entry gone, global setting takes effect

Git writes the local entry into every new worktree, and it hides the global
hook path that downstream skills rely on. The shared ``preflight`` entry point
calls this helper on its first tick, so the shadow clears with no failure the
caller ever sees.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_parent_directory = str(Path(__file__).resolve().parent)
if _parent_directory not in sys.path:
    sys.path.insert(0, _parent_directory)

from pr_loop_shared_constants.preflight_self_heal_constants import (  # noqa: E402
    ALL_GIT_CONFIG_GLOBAL_GET_ALL_HOOKS_PATH_COMMAND,
    ALL_GIT_CONFIG_LOCAL_GET_ALL_HOOKS_PATH_ARGUMENTS,
    ALL_GIT_CONFIG_LOCAL_UNSET_ALL_HOOKS_PATH_ARGUMENTS,
)


def _is_canonical_hooks_path_entry(
    raw_hooks_path_entry: str,
    expected_hooks_path_suffix: str,
) -> bool:
    """Return True when *raw_hooks_path_entry* matches the canonical hooks suffix.

    Args:
        raw_hooks_path_entry: A core.hooksPath entry as written in git config.
        expected_hooks_path_suffix: The canonical suffix the caller expects
            (the bugteam and shared callers each pass their own constant so
            the helper does not need to know which suffix is in force).

    Returns:
        True when, after Windows-to-POSIX separator normalization and trailing
        slash stripping, the entry ends with *expected_hooks_path_suffix*.
    """
    return (
        raw_hooks_path_entry.replace("\\", "/")
        .rstrip("/")
        .endswith(expected_hooks_path_suffix)
    )


def _canonical_global_hooks_path_is_set(expected_hooks_path_suffix: str) -> bool:
    """Return True when ``git config --global core.hooksPath`` has a canonical value.

    Reads the global scope with ``--get-all`` so a multi-valued global key
    does not produce a git "more than one value" exit code. Any one canonical
    entry among the global values is enough.

    Args:
        expected_hooks_path_suffix: The canonical suffix to check against.

    Returns:
        True when at least one global value normalizes to the canonical
        suffix; False when git is missing, the read fails, or no global value
        is canonical.
    """
    try:
        global_read_completed_process = subprocess.run(
            list(ALL_GIT_CONFIG_GLOBAL_GET_ALL_HOOKS_PATH_COMMAND),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (FileNotFoundError, OSError):
        return False
    if global_read_completed_process.returncode != 0:
        return False
    all_global_hooks_path_entries = [
        each_line.strip()
        for each_line in global_read_completed_process.stdout.splitlines()
        if each_line.strip()
    ]
    return any(
        _is_canonical_hooks_path_entry(
            each_global_hooks_path_entry, expected_hooks_path_suffix
        )
        for each_global_hooks_path_entry in all_global_hooks_path_entries
    )


def silently_clear_stale_local_hooks_path_override(
    repository_root: Path | None,
    expected_hooks_path_suffix: str,
) -> None:
    """Drop a worktree's stale local ``core.hooksPath`` when the global is canonical.

    ::

        local  core.hooksPath = <repo>/.git/hooks     (stale, wrong suffix)
        global core.hooksPath = <path>/.claude/hooks   (canonical)
        result: local entry unset, the global setting wins

        global also stale?  leave the local entry so the diagnostic still fires

    The unset runs only when a local entry is stale AND the global is already
    canonical. Every git error is swallowed, so an unrelated git failure never
    blocks preflight. The caller's later ``--get`` check still surfaces a real
    misconfiguration.

    Args:
        repository_root: Repository root to operate on; a None argument is a
            no-op so callers without a resolved root can call unconditionally.
        expected_hooks_path_suffix: The canonical suffix used to classify
            entries as canonical or stale.
    """
    if repository_root is None:
        return
    read_command: list[str] = ["git", "-C", str(repository_root)]
    read_command.extend(list(ALL_GIT_CONFIG_LOCAL_GET_ALL_HOOKS_PATH_ARGUMENTS))
    try:
        read_completed_process = subprocess.run(
            read_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (FileNotFoundError, OSError):
        return
    if read_completed_process.returncode != 0:
        return
    all_local_hooks_path_entries = [
        each_line.strip()
        for each_line in read_completed_process.stdout.splitlines()
        if each_line.strip()
    ]
    if not all_local_hooks_path_entries:
        return
    has_non_canonical_local_hooks_path_entry = any(
        not _is_canonical_hooks_path_entry(
            each_local_hooks_path_entry, expected_hooks_path_suffix
        )
        for each_local_hooks_path_entry in all_local_hooks_path_entries
    )
    if not has_non_canonical_local_hooks_path_entry:
        return
    if not _canonical_global_hooks_path_is_set(expected_hooks_path_suffix):
        return
    unset_command: list[str] = ["git", "-C", str(repository_root)]
    unset_command.extend(list(ALL_GIT_CONFIG_LOCAL_UNSET_ALL_HOOKS_PATH_ARGUMENTS))
    try:
        subprocess.run(
            unset_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (FileNotFoundError, OSError):
        return
