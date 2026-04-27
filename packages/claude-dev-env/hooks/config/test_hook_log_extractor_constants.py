"""Behavior tests for query-name pattern and exit-code routing contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from config import hook_log_extractor_constants
from config.hook_log_extractor_constants import (
    EXIT_CODE_ENVIRONMENT_MISSING,
    EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING,
    EXIT_CODE_SUCCESS,
    EXIT_CODE_UNKNOWN_QUERY,
    LOCK_MAXIMUM_RETRY_COUNT,
    LOCK_RETRY_SLEEP_SECONDS,
    QUERY_NAME_PATTERN,
    SENTINEL_INSERT_FAILURE_MESSAGE,
    SENTINEL_SELECT_FAILURE_MESSAGE,
    STOP_WRAPPER_DEBOUNCE_SECONDS,
    STOP_WRAPPER_LAST_RUN_TIMESTAMP_FILE,
    WINDOWS_CREATE_NEW_PROCESS_GROUP_FLAG,
    WINDOWS_DETACHED_PROCESS_FLAG,
)


def _matches_query_pattern(candidate_name: str) -> bool:
    return re.fullmatch(QUERY_NAME_PATTERN, candidate_name) is not None


def test_query_name_pattern_allows_canonical_pre_baked_query_name() -> None:
    assert _matches_query_pattern("top_blockers_last_24_hours")


def test_query_name_pattern_rejects_path_traversal() -> None:
    assert not _matches_query_pattern("../etc/passwd")


def test_query_name_pattern_rejects_uppercase() -> None:
    assert not _matches_query_pattern("TopBlockers")


def test_query_name_pattern_rejects_hyphens() -> None:
    assert not _matches_query_pattern("top-blockers")


def test_query_name_pattern_rejects_empty_string() -> None:
    assert not _matches_query_pattern("")


def test_unknown_query_exit_code_distinguishes_from_success() -> None:
    assert EXIT_CODE_UNKNOWN_QUERY != EXIT_CODE_SUCCESS


def test_unknown_query_exit_code_distinguishes_from_extractor_offline_fallback() -> None:
    assert EXIT_CODE_UNKNOWN_QUERY != EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING


def test_unknown_query_exit_code_distinguishes_from_init_environment_missing() -> None:
    assert EXIT_CODE_UNKNOWN_QUERY != EXIT_CODE_ENVIRONMENT_MISSING


def test_extractor_offline_fallback_matches_success_so_stop_hook_does_not_surface_failure() -> None:
    assert EXIT_CODE_EXTRACTOR_ENVIRONMENT_MISSING == EXIT_CODE_SUCCESS


def test_sentinel_insert_failure_message_is_distinct_from_select_failure() -> None:
    assert SENTINEL_INSERT_FAILURE_MESSAGE != SENTINEL_SELECT_FAILURE_MESSAGE
    assert SENTINEL_INSERT_FAILURE_MESSAGE


def test_resolver_falls_back_to_home_when_claude_home_is_empty(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CLAUDE_HOME", "")

    assert (
        hook_log_extractor_constants._resolve_claude_home_directory()
        == Path.home() / ".claude"
    )


def test_resolver_falls_back_to_home_when_claude_home_is_whitespace(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CLAUDE_HOME", "   ")

    assert (
        hook_log_extractor_constants._resolve_claude_home_directory()
        == Path.home() / ".claude"
    )


def test_lock_retry_constants_are_positive_and_bounded() -> None:
    assert LOCK_MAXIMUM_RETRY_COUNT > 0
    assert LOCK_RETRY_SLEEP_SECONDS > 0


def test_stop_wrapper_debounce_seconds_is_positive() -> None:
    assert STOP_WRAPPER_DEBOUNCE_SECONDS > 0


def test_stop_wrapper_last_run_timestamp_file_is_under_claude_home() -> None:
    expected_path = (
        hook_log_extractor_constants._resolve_claude_home_directory()
        / "logs"
        / "hooks"
        / ".state"
        / "stop_wrapper_last_run.txt"
    )
    assert Path(STOP_WRAPPER_LAST_RUN_TIMESTAMP_FILE) == expected_path


def test_windows_creation_flags_are_distinct_nonzero_bits() -> None:
    assert WINDOWS_DETACHED_PROCESS_FLAG > 0
    assert WINDOWS_CREATE_NEW_PROCESS_GROUP_FLAG > 0
    assert (
        WINDOWS_DETACHED_PROCESS_FLAG & WINDOWS_CREATE_NEW_PROCESS_GROUP_FLAG
    ) == 0
