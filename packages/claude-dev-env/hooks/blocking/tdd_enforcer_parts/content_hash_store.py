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

import contextlib
import hashlib
import json
import os
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

from atomic_file_writer import write_text_atomically
from hooks_constants.session_edit_stage_gate_constants import (
    LOCK_ACQUIRE_RETRY_SECONDS,
    LOCK_ACQUIRE_TIMEOUT_SECONDS,
    SESSION_EDIT_LOCK_FILE_SUFFIX,
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
    STORED_FAILED_AT_KEY,
    STORED_FAILURE_COMMAND_KEY,
    STORED_FAILURE_EXIT_STATUS_KEY,
    STORED_FAILURE_HASH_KEY,
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


def _acquire_state_file_lock(lock_file: Path) -> int | None:
    """Grab an exclusive per-store lock, spinning until it frees or times out.

    Mirrors session_file_edit_tracker's best-effort lock: a caller that
    cannot acquire it within the timeout proceeds without it rather than
    stalling the hook that triggered the read-modify-write.
    """
    lock_acquire_deadline = time.monotonic() + LOCK_ACQUIRE_TIMEOUT_SECONDS
    while time.monotonic() < lock_acquire_deadline:
        try:
            return os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            time.sleep(LOCK_ACQUIRE_RETRY_SECONDS)
    return None


@contextlib.contextmanager
def _hold_state_file_lock(state_file: Path) -> Iterator[None]:
    """Hold a per-(session, repository root) lock across one read-modify-write.

    Two writers share this exact file: the gate's own qualifying-first-sight
    tracking, and a PostToolUse hook recording a failing test run. Both take
    this lock across their round trip so neither writer's update is lost to
    the other's concurrent read-modify-write. _atomic_write_state already
    writes via tempfile-plus-replace, so the file itself is never torn; this
    lock closes the separate lost-update race between two writers.
    """
    lock_file = state_file.with_name(state_file.name + SESSION_EDIT_LOCK_FILE_SUFFIX)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_descriptor = _acquire_state_file_lock(lock_file)
    try:
        yield
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
            lock_file.unlink(missing_ok=True)


def _has_matching_recorded_failure(
    stored_entry: object, current_hash: str, current_time: float, freshness_seconds: int
) -> bool:
    """Return whether a recorded test failure still evidences the candidate's content.

    A failure counts as evidence only while the candidate's content is
    exactly what failed and the record has not aged past the freshness
    window -- editing the test again, or letting the record go stale, drops
    it as evidence and falls back to the ordinary content-hash tracking.
    """
    if not isinstance(stored_entry, dict):
        return False
    if stored_entry.get(STORED_FAILURE_HASH_KEY) != current_hash:
        return False
    failed_at = stored_entry.get(STORED_FAILED_AT_KEY)
    if not isinstance(failed_at, (int, float)):
        return False
    return current_time - failed_at <= freshness_seconds


def _is_qualifying_first_sight(
    candidate_path: Path, candidate_text: str, current_time: float, freshness_seconds: int
) -> bool:
    candidate_mtime = freshness._safe_mtime(candidate_path)
    if candidate_mtime is None or current_time - candidate_mtime > freshness_seconds:
        return False
    if not freshness.has_test_evidence_in(candidate_text):
        return False
    return git_tracking.has_uncommitted_change_from_head(candidate_path)


def _first_sight_decision(
    candidate_path: Path,
    candidate_text: str,
    current_time: float,
    freshness_seconds: int,
    current_hash: str,
) -> tuple[bool, dict[str, object] | None]:
    if not _is_qualifying_first_sight(
        candidate_path, candidate_text, current_time, freshness_seconds
    ):
        return False, None
    return True, _recorded_entry(current_hash, current_time)


def _content_hash_decision(
    all_stored_entry_fields: dict[str, object],
    current_hash: str,
    current_time: float,
    freshness_seconds: int,
) -> tuple[bool, dict[str, object] | None]:
    if current_hash != all_stored_entry_fields.get(STORED_CONTENT_HASH_KEY):
        return True, _recorded_entry(current_hash, current_time)
    stored_changed_at = all_stored_entry_fields.get(STORED_CHANGED_AT_KEY)
    if not isinstance(stored_changed_at, (int, float)):
        return False, None
    return current_time - stored_changed_at <= freshness_seconds, None


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
    if _has_matching_recorded_failure(
        stored_entry, current_hash, current_time, freshness_seconds
    ):
        return True, None
    if not isinstance(stored_entry, dict) or STORED_CONTENT_HASH_KEY not in stored_entry:
        return _first_sight_decision(
            candidate_path, candidate_text, current_time, freshness_seconds, current_hash
        )
    return _content_hash_decision(stored_entry, current_hash, current_time, freshness_seconds)


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
            each_candidate,
            all_stored_hashes.get(candidate_key),
            current_time,
            freshness_seconds,
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
        session_id: Raw session_id from the hook payload.
        repository_root: Raw cwd from the hook payload.
        freshness_seconds: Maximum age, in seconds, a stored hash may have.

    Returns:
        True when at least one candidate carries a matching recorded test
        failure, is a fresh dirty first sighting, has a recorded hash that
        now differs, or has a recorded hash still in window.
    """
    state_file = _state_file_path(session_id, repository_root)
    with _hold_state_file_lock(state_file):
        all_stored_hashes = _load_state(state_file)
        is_allowed, state_changed = _apply_candidate_decisions(
            all_candidates, all_stored_hashes, time.time(), freshness_seconds
        )
        if state_changed:
            _atomic_write_state(state_file, all_stored_hashes)
    return is_allowed


def _merged_failure_entry(
    existing_entry: object,
    candidate_text: str,
    command: str,
    exit_status: int,
    current_time: float,
) -> dict[str, object]:
    merged_entry = dict(existing_entry) if isinstance(existing_entry, dict) else {}
    merged_entry[STORED_FAILURE_HASH_KEY] = _content_hash(candidate_text)
    merged_entry[STORED_FAILED_AT_KEY] = current_time
    merged_entry[STORED_FAILURE_COMMAND_KEY] = command
    merged_entry[STORED_FAILURE_EXIT_STATUS_KEY] = exit_status
    return merged_entry


def _record_one_test_file_failure(
    test_file_path: Path,
    all_stored_hashes: dict[str, object],
    command: str,
    exit_status: int,
    current_time: float,
) -> bool:
    candidate_text = freshness._read_candidate_text(test_file_path)
    if candidate_text is None:
        return False
    candidate_key = _state_key_for(test_file_path)
    all_stored_hashes[candidate_key] = _merged_failure_entry(
        all_stored_hashes.get(candidate_key),
        candidate_text,
        command,
        exit_status,
        current_time,
    )
    return True


def record_test_command_failure(
    all_test_file_paths: list[Path],
    command: str,
    exit_status: int,
    session_id: str,
    repository_root: str,
) -> None:
    """Record a failing test command as gate evidence, one entry per test file.

    Keyed exactly as the gate looks candidates up, so a failure satisfies the
    gate only for the file it names, never a sibling the command also ran.
    Existing content-hash fields on that entry are preserved, not overwritten.
    """
    state_file = _state_file_path(session_id, repository_root)
    current_time = time.time()
    with _hold_state_file_lock(state_file):
        all_stored_hashes = _load_state(state_file)
        all_recorded = [
            _record_one_test_file_failure(
                each_path, all_stored_hashes, command, exit_status, current_time
            )
            for each_path in all_test_file_paths
        ]
        if any(all_recorded):
            _atomic_write_state(state_file, all_stored_hashes)
