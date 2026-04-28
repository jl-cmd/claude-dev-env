#!/usr/bin/env python3
"""SessionStart hook — clean the Claude Code session-env directory on Windows.

Claude Code's Bash tool sets up a per-session sandbox at
``~/.claude/session-env/<session_id>/``. The mkdir call appears non-recursive,
so once the directory exists, later Bash invocations in the same session can
throw ``EEXIST`` and abort. PowerShell tool calls are unaffected.

This hook removes the current session's pre-existing directory at start and
prunes sibling entries whose mtime is older than the stale-age threshold so
the parent directory does not grow without bound.

Tracking: https://github.com/anthropics/claude-code/issues — Windows-only
mkdir bug separate from the EEXIST fixes in v2.1.70-v2.1.72.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path
from typing import Callable


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.session_env_cleanup_constants import (
    RMTREE_ONEXC_PYTHON_VERSION,
    SESSION_ENV_DIRECTORY,
    SESSION_ID_PATTERN,
    STALE_AGE_SECONDS,
    WINDOWS_PLATFORM_TAG,
)


def _strip_read_only_and_retry(
    removal_function: Callable[[str], None],
    target_path: str,
    *_unused_exception_info: object,
) -> None:
    try:
        os.chmod(target_path, stat.S_IWRITE)
        removal_function(target_path)
    except OSError:
        pass


def _force_rmtree(target_path: str) -> None:
    rmtree_onexc_python_version = RMTREE_ONEXC_PYTHON_VERSION
    try:
        if sys.version_info >= rmtree_onexc_python_version:
            shutil.rmtree(target_path, onexc=_strip_read_only_and_retry)
        else:
            shutil.rmtree(target_path, onerror=_strip_read_only_and_retry)
    except OSError:
        pass


def prune_session_env(
    session_env_directory: str,
    session_id: str,
    stale_age_seconds: float,
) -> None:
    """Remove the current session's directory and prune stale siblings."""
    if session_id:
        current_session_path = os.path.join(session_env_directory, session_id)
        if os.path.isdir(current_session_path):
            _force_rmtree(current_session_path)
    if not os.path.isdir(session_env_directory):
        return
    stale_cutoff_seconds = time.time() - stale_age_seconds
    try:
        all_entry_names = os.listdir(session_env_directory)
    except OSError:
        return
    for each_entry_name in all_entry_names:
        entry_path = os.path.join(session_env_directory, each_entry_name)
        try:
            entry_mtime_seconds = os.path.getmtime(entry_path)
        except OSError:
            continue
        if entry_mtime_seconds >= stale_cutoff_seconds:
            continue
        _force_rmtree(entry_path)


def _read_session_id_from_stdin() -> str:
    session_id_pattern = SESSION_ID_PATTERN
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    raw_session_id = payload.get("session_id")
    if not isinstance(raw_session_id, str):
        return ""
    if not session_id_pattern.match(raw_session_id):
        return ""
    return raw_session_id


def main() -> None:
    windows_platform_tag = WINDOWS_PLATFORM_TAG
    if sys.platform != windows_platform_tag:
        return
    session_env_directory = SESSION_ENV_DIRECTORY
    stale_age_seconds = STALE_AGE_SECONDS
    session_id = _read_session_id_from_stdin()
    prune_session_env(
        session_env_directory=session_env_directory,
        session_id=session_id,
        stale_age_seconds=stale_age_seconds,
    )


if __name__ == "__main__":
    main()
