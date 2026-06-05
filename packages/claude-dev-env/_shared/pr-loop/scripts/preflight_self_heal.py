"""Self-heal helper for stale local-scope ``core.hooksPath`` overrides.

Git seeds ``core.hooksPath = <repo>/.git/hooks`` into every new worktree's
local config. That repo-local entry shadows the correct global setting and
breaks downstream hook-dependent skills. The helper here is called from both
:mod:`bugteam_preflight` (skill-local) and :mod:`preflight` (shared) so the
shadowing entry is cleared the first time preflight runs against a fresh
worktree, without any caller-visible failure.
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
    """Remove every stale, non-canonical local-scope core.hooksPath override.

    The unset runs only when BOTH conditions hold: at least one local-scope
    entry is non-canonical, AND a canonical global setting is already
    configured. When the global is unset or non-canonical, the helper stands
    down so the downstream ``core.hooksPath is '<path>'`` diagnostic stays
    informative and the auto-remediation script can repair the global from a
    known starting point.

    Silent on every git outcome — read errors, write errors, and process
    launch errors are all suppressed so an unrelated git failure cannot block
    preflight. The caller's subsequent ``--get`` verification step surfaces
    the final config state through the normal failure path, so a real
    misconfiguration is still reported with the canonical
    ``core.hooksPath is '<path>'`` diagnostic.

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
