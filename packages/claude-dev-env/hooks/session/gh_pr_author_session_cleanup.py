#!/usr/bin/env python3
"""SessionStart hook — sweep stale gh-pr-author swap state files at session start.

The PreToolUse enforcer (``gh_pr_author_enforcer.py``) writes a per-session
state file recording the original gh CLI account before swapping to
``GITHUB_DEFAULT_ACCOUNT``. The PostToolUse companion
(``gh_pr_author_restore.py``) reads that file and switches back when
``gh pr create`` finishes. When a session is interrupted between the
swap and the restore — a crash, a downstream PreToolUse deny that fires
*after* the enforcer's swap completed, or any other path that skips
PostToolUse — the user is left on ``GITHUB_DEFAULT_ACCOUNT`` with a
stale state file on disk.

This hook runs at the start of every Claude Code session. When
``GITHUB_DEFAULT_ACCOUNT`` is set, it scans ``tempfile.gettempdir()``
for every file matching ``{STATE_FILE_PREFIX}*{STATE_FILE_SUFFIX}``,
reads the original account from each, runs ``gh auth switch --user
<original>``, and deletes the file. A state file whose switch fails is
left in place so the next session can retry. The hook is a strict no-op
when ``GITHUB_DEFAULT_ACCOUNT`` is unset, so users who have not opted
into the swap workflow are completely unaffected.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

hooks_parent_directory = str(Path(__file__).resolve().parent.parent)
if hooks_parent_directory not in sys.path:
    sys.path.insert(0, hooks_parent_directory)

from _gh_pr_author_swap_utils import (  # noqa: E402
    _delete_state_file,
    _lstat_indicates_attacker_planted,
    _read_original_account,
    _switch_gh_account,
    _write_line,
)
from hooks_constants.gh_pr_author_swap_constants import (  # noqa: E402
    REQUIRED_ACCOUNT_ENV_VAR,
    STATE_FILE_PREFIX,
    STATE_FILE_STALE_AGE_SECONDS,
    STATE_FILE_SUFFIX,
)


def _collect_stale_state_files(temp_directory: Path) -> list[Path]:
    """Return swap-state files older than the stale threshold and safe to process.

    A state file younger than ``STATE_FILE_STALE_AGE_SECONDS`` is
    treated as belonging to a concurrent Claude Code session that may
    still be mid-``gh pr create``. Sweeping such a file would steal the
    active session's restore target. Files older than the threshold are
    overwhelmingly likely to be stale — the enforcer-to-restore window
    is bounded by the gh subprocess timeouts (10s switch + 5s api user
    + filesystem work), so any file older than
    ``STATE_FILE_STALE_AGE_SECONDS`` is past the longest plausible
    active window.

    Each candidate is also screened for ownership and permission bits
    matching the enforcer's write contract. A file with mode bits other
    than ``STATE_FILE_PERMISSION_MODE`` or (on POSIX) owned by a
    different user is silently skipped — it was not written by an
    enforcer running as the current user and must not be allowed to
    drive ``gh auth switch``.

    The candidate is inspected via ``lstat`` rather than ``stat`` so a
    symlink at the predictable swap-state path is screened on its own
    metadata, not on whatever the symlink resolves to. Any entry that
    is not a regular file (symlink, socket, fifo, device) is silently
    skipped. The enforcer creates state files with ``O_NOFOLLOW``;
    mirroring that contract here closes the symlink-hijack window where
    an attacker plants a symlink pointing to a legitimate 0o600 file
    owned by the current user to trick the cleanup hook into reading
    that file as a swap-state payload.

    Returned paths are sorted by modification time in ascending order so
    that when the caller iterates and runs ``gh auth switch`` for each
    file, the newest stale file is processed LAST. ``gh auth switch``
    is global state — only the last switch wins — so processing the
    newest file last leaves the gh CLI on the most recently captured
    original account when multiple sessions crashed with different
    original accounts. The single ``lstat`` syscall performed per
    candidate is reused for both the attacker-planted screen and the
    mtime ordering key so the sort does not double-stat.

    Args:
        temp_directory: System temp directory returned by
            ``tempfile.gettempdir()``.

    Returns:
        List of swap-state file paths that are regular files whose
        modification time is older than ``STATE_FILE_STALE_AGE_SECONDS``
        seconds before now and whose ownership/mode bits match the
        enforcer's write contract. Sorted by mtime ascending so the
        newest stale file is last in iteration order. Empty list when
        the temp directory cannot be listed.
    """
    glob_pattern = f"{STATE_FILE_PREFIX}*{STATE_FILE_SUFFIX}"
    current_time_seconds = time.time()
    all_stale_candidates_with_mtime: list[tuple[float, Path]] = []
    try:
        all_candidate_paths = list(temp_directory.glob(glob_pattern))
    except OSError:
        return []
    for each_candidate_path in all_candidate_paths:
        try:
            file_lstat_result = each_candidate_path.lstat()
        except OSError:
            continue
        if _lstat_indicates_attacker_planted(file_lstat_result):
            continue
        file_age_seconds = current_time_seconds - file_lstat_result.st_mtime
        if file_age_seconds >= STATE_FILE_STALE_AGE_SECONDS:
            all_stale_candidates_with_mtime.append(
                (file_lstat_result.st_mtime, each_candidate_path)
            )
    all_stale_candidates_with_mtime.sort(key=lambda each_mtime_path_pair: each_mtime_path_pair[0])
    return [each_mtime_path_pair[1] for each_mtime_path_pair in all_stale_candidates_with_mtime]


def _restore_stale_state_file(state_file: Path) -> None:
    """Restore one stale state file: switch back, then delete on success.

    A malformed state file is deleted without a switch attempt. A
    well-formed file whose switch attempt fails is left on disk so the
    next session-start can retry.

    Args:
        state_file: Absolute path to a candidate state file.
    """
    original_account = _read_original_account(state_file)
    if original_account is None:
        _delete_state_file(state_file)
        return
    has_switched_account = _switch_gh_account(original_account)
    if has_switched_account:
        _delete_state_file(state_file)
    else:
        _write_line(
            f"[gh-pr-author-cleanup] failed to restore active gh account to {original_account!r} from "
            f"stale state file {state_file}; left in place for next session",
            sys.stderr,
        )


def main() -> None:
    """Sweep stale gh-pr-author swap state files when the workflow is enabled.

    Exits 0 in every path. When ``GITHUB_DEFAULT_ACCOUNT`` is unset the
    hook returns immediately so users who have not opted into the swap
    workflow see no behavior change. Otherwise iterates every matching
    state file under ``tempfile.gettempdir()`` and restores each one
    independently — a failure on one file does not block the others.
    """
    required_account = os.environ.get(REQUIRED_ACCOUNT_ENV_VAR, "").strip()
    if not required_account:
        return
    temp_directory = Path(tempfile.gettempdir())
    all_stale_state_files = _collect_stale_state_files(temp_directory)
    for each_state_file in all_stale_state_files:
        _restore_stale_state_file(each_state_file)


if __name__ == "__main__":
    main()
