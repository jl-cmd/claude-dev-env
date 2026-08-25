"""Production-path staging tests for the session-edit stage gate."""

from __future__ import annotations

import sys
from pathlib import Path

_TEST_DIRECTORY = Path(__file__).resolve().parent
if str(_TEST_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TEST_DIRECTORY))

from test_session_edit_stage_gate_support import (  # noqa: E402
    make_test_directories,
    parse_dispatcher_decision,
    prepare_repository_with_unstaged_edit,
    run_bash_dispatcher,
    run_tracker_event,
    read_tracker_paths,
)

SESSION_ID = "staging-production-session"


def test_dispatcher_denies_tracker_recorded_unstaged_edit(tmp_path: Path) -> None:
    """The Bash dispatcher denies a commit for a tracker-recorded edit."""
    repository_root, temp_directory, home_directory = make_test_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    tracker_run = run_tracker_event(
        tracked_file, SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert tracker_run.returncode == 0
    assert read_tracker_paths(temp_directory, SESSION_ID) == [str(tracked_file.resolve())]

    dispatcher_run = run_bash_dispatcher(
        "git commit -m update",
        SESSION_ID,
        repository_root,
        temp_directory,
        home_directory,
    )
    assert dispatcher_run.returncode == 0
    decision, reason = parse_dispatcher_decision(dispatcher_run.stdout)
    assert decision == "deny"
    assert "widget.py" in reason


def test_dispatcher_allows_specific_staging_segment(tmp_path: Path) -> None:
    """The Bash dispatcher accepts a commit preceded by a specific git add."""
    repository_root, temp_directory, home_directory = make_test_directories(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    tracker_run = run_tracker_event(
        tracked_file, SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert tracker_run.returncode == 0

    dispatcher_run = run_bash_dispatcher(
        "git add widget.py && git commit -m update",
        SESSION_ID,
        repository_root,
        temp_directory,
        home_directory,
    )
    assert dispatcher_run.returncode == 0
    assert parse_dispatcher_decision(dispatcher_run.stdout) == ("", "")
