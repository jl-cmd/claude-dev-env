"""Persist each candidate test file's last-observed content hash per session.

The freshness check alone cannot tell a real test edit from a bare touch:
both refresh the file's mtime, so a touch reopens the TDD gate for every
production write it looks at afterward. This module remembers what a
candidate test file contained the last time the gate looked at it, keyed by
session and repository root, so a touch that leaves the content unchanged no
longer satisfies the gate.

::

    first sight, dirty + fresh + real test -> allow, record hash + time
    first sight, otherwise                 -> deny, record nothing
    seen before, hash now differs          -> allow, record new hash + time
    seen before, hash matches, in window   -> allow (green/refactor continues)
    seen before, hash matches, expired     -> deny

The state lives in one JSON file per (session, repository root) pair under the
OS temp directory, shaped like the per-session tracker in
hooks/observability/session_file_edit_tracker.py, so two worktrees open in one
session never share a file.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from pathlib import Path

from atomic_file_writer import write_text_atomically
from hooks_constants.session_edit_stage_gate_constants import (
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
    STATE_FILE_ATOMIC_WRITE_SUFFIX,
    STATE_FILE_DEFAULT_SESSION_ID,
    STATE_FILE_JSON_INDENT_SPACES,
)
from hooks_constants.setup_project_paths_constants import UTF8_ENCODING
from json_file_reader import read_json_object
from tdd_enforcer_parts import freshness, git_tracking
from tdd_enforcer_parts.config.tdd_enforcer_constants import (
    HASH_STATE_FILE_PREFIX,
    HASH_STATE_FILE_SUFFIX,
    REPOSITORY_ROOT_DIGEST_LENGTH,
    STORED_CHANGED_AT_KEY,
    STORED_CONTENT_HASH_KEY,
)


def _sanitized_session_id(session_id: str) -> str:
    sanitized_session_id = SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)
    return sanitized_session_id or STATE_FILE_DEFAULT_SESSION_ID


def _repository_root_digest(repository_root: str) -> str:
    full_digest = hashlib.sha256(repository_root.encode("utf-8")).hexdigest()
    return full_digest[:REPOSITORY_ROOT_DIGEST_LENGTH]


def _state_file_path(session_id: str, repository_root: str) -> Path:
    file_name = (
        f"{HASH_STATE_FILE_PREFIX}{_sanitized_session_id(session_id)}-"
        f"{_repository_root_digest(repository_root)}{HASH_STATE_FILE_SUFFIX}"
    )
    return Path(tempfile.gettempdir()) / file_name


def _state_key_for(candidate_path: Path) -> str:
    try:
        return str(candidate_path.resolve())
    except OSError:
        return str(candidate_path)


def _load_state(state_file: Path) -> dict[str, object]:
    return read_json_object(state_file, encoding=UTF8_ENCODING) or {}


def _atomic_write_state(state_file: Path, all_stored_hashes: dict[str, object]) -> None:
    write_text_atomically(
        state_file,
        json.dumps(all_stored_hashes, indent=STATE_FILE_JSON_INDENT_SPACES),
        encoding=UTF8_ENCODING,
        temporary_prefix=HASH_STATE_FILE_PREFIX,
        temporary_suffix=STATE_FILE_ATOMIC_WRITE_SUFFIX,
        should_reap_orphans=False,
    )


def _content_hash(candidate_text: str) -> str:
    return hashlib.sha256(candidate_text.encode(UTF8_ENCODING)).hexdigest()


def _recorded_entry(current_hash: str, current_time: float) -> dict[str, object]:
    return {STORED_CONTENT_HASH_KEY: current_hash, STORED_CHANGED_AT_KEY: current_time}


def _is_qualifying_first_sight(
    candidate_path: Path, candidate_text: str, current_time: float, freshness_seconds: int
) -> bool:
    candidate_mtime = freshness._safe_mtime(candidate_path)
    if candidate_mtime is None or current_time - candidate_mtime > freshness_seconds:
        return False
    if not freshness.has_test_evidence_in(candidate_text):
        return False
    return git_tracking.has_uncommitted_change_from_head(candidate_path)


def _evaluate_candidate(
    candidate_path: Path,
    stored_entry: object,
    current_time: float,
    freshness_seconds: int,
) -> tuple[bool, dict[str, object] | None]:
    candidate_text = freshness._read_candidate_text(candidate_path)
    if candidate_text is None:
        return False, None
    current_hash = _content_hash(candidate_text)
    if not isinstance(stored_entry, dict):
        if _is_qualifying_first_sight(
            candidate_path, candidate_text, current_time, freshness_seconds
        ):
            return True, _recorded_entry(current_hash, current_time)
        return False, None
    if current_hash != stored_entry.get(STORED_CONTENT_HASH_KEY):
        return True, _recorded_entry(current_hash, current_time)
    stored_changed_at = stored_entry.get(STORED_CHANGED_AT_KEY)
    if not isinstance(stored_changed_at, (int, float)):
        return False, None
    return current_time - stored_changed_at <= freshness_seconds, None


def _apply_candidate_decisions(
    all_candidates: list[Path],
    all_stored_hashes: dict[str, object],
    current_time: float,
    freshness_seconds: int,
) -> tuple[bool, bool]:
    is_allowed = False
    state_changed = False
    for each_candidate in all_candidates:
        candidate_key = _state_key_for(each_candidate)
        candidate_allowed, updated_entry = _evaluate_candidate(
            each_candidate, all_stored_hashes.get(candidate_key), current_time, freshness_seconds
        )
        if candidate_allowed:
            is_allowed = True
        if updated_entry is not None:
            all_stored_hashes[candidate_key] = updated_entry
            state_changed = True
    return is_allowed, state_changed


def has_recorded_or_fresh_test(
    all_candidates: list[Path],
    session_id: str,
    repository_root: str,
    freshness_seconds: int,
) -> bool:
    """Return whether any candidate's tracked content hash satisfies the gate.

    Args:
        all_candidates: Candidate test paths for the production file.
        session_id: Raw ``session_id`` from the hook payload.
        repository_root: Raw ``cwd`` from the hook payload.
        freshness_seconds: Maximum age, in seconds, a stored hash may have.

    Returns:
        True when at least one candidate is a fresh, dirty first sighting, a
        recorded hash that now differs, or a recorded hash still in window.
    """
    state_file = _state_file_path(session_id, repository_root)
    all_stored_hashes = _load_state(state_file)
    is_allowed, state_changed = _apply_candidate_decisions(
        all_candidates, all_stored_hashes, time.time(), freshness_seconds
    )
    if state_changed:
        _atomic_write_state(state_file, all_stored_hashes)
    return is_allowed
