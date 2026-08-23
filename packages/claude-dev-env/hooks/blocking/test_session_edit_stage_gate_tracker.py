"""Production-path tracker event-order tests for the session-edit stage gate."""

from __future__ import annotations

import sys
from pathlib import Path

_TEST_DIRECTORY = Path(__file__).resolve().parent
if str(_TEST_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TEST_DIRECTORY))

from test_session_edit_stage_gate import (  # noqa: E402
    _make_directories,
    parse_dispatcher_decision,
    prepare_repository_with_two_unstaged_edits,
    read_tracker_paths,
    run_bash_dispatcher,
    run_tracker_event,
)

SESSION_ID = "tracker-production-session"


def test_tracker_events_precede_dispatcher_stage_decision(tmp_path: Path) -> None:
    """The dispatcher sees every edit recorded before the commit event."""
    repository_root, temp_directory, home_directory = _make_directories(tmp_path)
    tracked_file, second_file = prepare_repository_with_two_unstaged_edits(repository_root)
    for each_file in (tracked_file, second_file):
        tracker_run = run_tracker_event(
            each_file, SESSION_ID, repository_root, temp_directory, home_directory
        )
        assert tracker_run.returncode == 0

    assert read_tracker_paths(temp_directory, SESSION_ID) == [
        str(tracked_file.resolve()),
        str(second_file.resolve()),
    ]

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
    assert "second_widget.py" in reason
