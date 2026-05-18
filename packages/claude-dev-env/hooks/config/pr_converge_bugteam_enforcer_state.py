"""Shared state-loading helpers for the pr_converge_bugteam_enforcer hook pair.

Both the enforcer (``pr_converge_bugteam_enforcer.py``) and the tracker
(``pr_converge_bugteam_skill_tracker.py``) read the per-job
``$CLAUDE_JOB_DIR/pr-converge-state.json`` file from the same per-job
directory. This module hosts the byte-identical ``load_state_dictionary``
and ``resolve_state_path`` helpers so each hook imports a single canonical
definition.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from config.pr_converge_bugteam_enforcer_constants import (
    CLAUDE_JOB_DIR_ENV_VAR,
    PR_CONVERGE_STATE_FILENAME,
)


def load_state_dictionary(state_path: Path) -> dict[str, object] | None:
    """Return the parsed pr-converge state, or None when absent or unparseable.

    Args:
        state_path: Absolute path to ``pr-converge-state.json``.

    Returns:
        The decoded state dictionary, or None when the file is missing,
        malformed, empty, or not a JSON object at the root.
    """
    if not state_path.is_file():
        return None
    try:
        raw_text = state_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not raw_text.strip():
        return None
    try:
        parsed_state = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_state, dict):
        return None
    return parsed_state


def resolve_state_path() -> Path | None:
    """Return the absolute path to the per-job ``pr-converge-state.json``.

    Reads ``$CLAUDE_JOB_DIR`` from the environment and joins
    ``PR_CONVERGE_STATE_FILENAME`` onto it. The path is returned even when
    the file does not yet exist on disk; callers are expected to call
    ``load_state_dictionary`` (or ``state_path.is_file()``) to check for
    presence.

    Returns:
        Absolute path to ``$CLAUDE_JOB_DIR/pr-converge-state.json``, or
        ``None`` when the ``CLAUDE_JOB_DIR`` environment variable is unset
        or empty (no single-PR pr-converge job is currently active).
    """
    job_directory = os.environ.get(CLAUDE_JOB_DIR_ENV_VAR, "")
    if not job_directory:
        return None
    return Path(job_directory) / PR_CONVERGE_STATE_FILENAME
