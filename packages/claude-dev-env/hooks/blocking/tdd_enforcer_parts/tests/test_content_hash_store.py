"""Behavioral tests for the content_hash_store parts module."""

import json
import os
import time
from pathlib import Path

from tdd_enforcer_parts import content_hash_store


def _write_fresh_test_file(directory: Path, content: str = "def test_fulfill(): pass\n") -> Path:
    candidate = directory / "test_orders.py"
    candidate.write_text(content)
    return candidate


def test_state_file_path_differs_by_repository_root(tmp_path: Path) -> None:
    first_root_path = content_hash_store._state_file_path("session-a", str(tmp_path / "one"))
    second_root_path = content_hash_store._state_file_path("session-a", str(tmp_path / "two"))
    assert first_root_path != second_root_path


def test_state_file_path_is_stable_for_the_same_inputs(tmp_path: Path) -> None:
    first_lookup = content_hash_store._state_file_path("session-a", str(tmp_path))
    second_lookup = content_hash_store._state_file_path("session-a", str(tmp_path))
    assert first_lookup == second_lookup


def test_first_sight_allows_and_stores_a_fresh_dirty_test(tmp_path: Path) -> None:
    candidate = _write_fresh_test_file(tmp_path)

    is_allowed = content_hash_store.has_recorded_or_fresh_test(
        [candidate], "session-1", str(tmp_path), 600
    )

    assert is_allowed is True
    state_file = content_hash_store._state_file_path("session-1", str(tmp_path))
    state = json.loads(state_file.read_text())
    assert content_hash_store._state_key_for(candidate) in state


def test_first_sight_denies_when_test_evidence_is_missing(tmp_path: Path) -> None:
    candidate = _write_fresh_test_file(tmp_path, content="orders = 'not a test'\n")

    is_allowed = content_hash_store.has_recorded_or_fresh_test(
        [candidate], "session-2", str(tmp_path), 600
    )

    assert is_allowed is False


def test_first_sight_denies_when_test_file_is_stale(tmp_path: Path) -> None:
    candidate = _write_fresh_test_file(tmp_path)
    stale_timestamp = time.time() - 700
    os.utime(candidate, (stale_timestamp, stale_timestamp))

    is_allowed = content_hash_store.has_recorded_or_fresh_test(
        [candidate], "session-3", str(tmp_path), 600
    )

    assert is_allowed is False


def test_second_sight_denies_a_touch_that_leaves_content_unchanged(tmp_path: Path) -> None:
    candidate = _write_fresh_test_file(tmp_path)
    session_id, repository_root = "session-4", str(tmp_path)
    assert content_hash_store.has_recorded_or_fresh_test(
        [candidate], session_id, repository_root, 600
    )
    state_file = content_hash_store._state_file_path(session_id, repository_root)
    state = json.loads(state_file.read_text())
    candidate_key = content_hash_store._state_key_for(candidate)
    state[candidate_key][content_hash_store.STORED_CHANGED_AT_KEY] -= 700
    state_file.write_text(json.dumps(state))
    candidate.touch()

    is_allowed = content_hash_store.has_recorded_or_fresh_test(
        [candidate], session_id, repository_root, 600
    )

    assert is_allowed is False


def test_second_sight_allows_when_content_actually_changed_after_the_window(
    tmp_path: Path,
) -> None:
    candidate = _write_fresh_test_file(tmp_path)
    session_id, repository_root = "session-5", str(tmp_path)
    assert content_hash_store.has_recorded_or_fresh_test(
        [candidate], session_id, repository_root, 600
    )
    state_file = content_hash_store._state_file_path(session_id, repository_root)
    state = json.loads(state_file.read_text())
    candidate_key = content_hash_store._state_key_for(candidate)
    state[candidate_key][content_hash_store.STORED_CHANGED_AT_KEY] -= 700
    state_file.write_text(json.dumps(state))
    candidate.write_text("def test_fulfill(): assert True\n")

    is_allowed = content_hash_store.has_recorded_or_fresh_test(
        [candidate], session_id, repository_root, 600
    )

    assert is_allowed is True


def test_second_sight_allows_a_repeat_write_within_the_window_untouched(
    tmp_path: Path,
) -> None:
    candidate = _write_fresh_test_file(tmp_path)
    session_id, repository_root = "session-6", str(tmp_path)
    assert content_hash_store.has_recorded_or_fresh_test(
        [candidate], session_id, repository_root, 600
    )

    is_allowed = content_hash_store.has_recorded_or_fresh_test(
        [candidate], session_id, repository_root, 600
    )

    assert is_allowed is True


def test_any_candidate_satisfying_the_gate_allows_the_write(tmp_path: Path) -> None:
    stale_candidate = _write_fresh_test_file(tmp_path)
    stale_timestamp = time.time() - 700
    os.utime(stale_candidate, (stale_timestamp, stale_timestamp))
    fresh_candidate = tmp_path / "orders_test.py"
    fresh_candidate.write_text("def test_fulfill(): pass\n")

    is_allowed = content_hash_store.has_recorded_or_fresh_test(
        [stale_candidate, fresh_candidate], "session-7", str(tmp_path), 600
    )

    assert is_allowed is True


def test_denies_when_no_candidate_file_exists(tmp_path: Path) -> None:
    missing_candidate = tmp_path / "test_missing.py"

    is_allowed = content_hash_store.has_recorded_or_fresh_test(
        [missing_candidate], "session-8", str(tmp_path), 600
    )

    assert is_allowed is False
