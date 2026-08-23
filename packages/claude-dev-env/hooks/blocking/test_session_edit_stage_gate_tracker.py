"""Production-path tracker event-order tests for the session-edit stage gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TEST_DIRECTORY = Path(__file__).resolve().parent
if str(_TEST_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TEST_DIRECTORY))

from test_session_edit_stage_gate_support import (  # noqa: E402
    make_test_directories,
    make_process_repository,
    parse_dispatcher_decision,
    prepare_process_child_repository,
    prepare_repository_with_unstaged_edit,
    prepare_repository_with_two_unstaged_edits,
    read_tracker_paths,
    run_bash_dispatcher,
    run_tracker_event,
)

SESSION_ID = "tracker-production-session"


def test_tracker_events_precede_dispatcher_stage_decision(tmp_path: Path) -> None:
    """The dispatcher sees every edit recorded before the commit event."""
    repository_root, temp_directory, home_directory = make_test_directories(tmp_path)
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


def test_dispatcher_uses_event_cwd_when_process_runs_elsewhere(tmp_path: Path) -> None:
    """The dispatcher passes event cwd so the gate inspects the event repository."""
    repository_root, temp_directory, home_directory = make_test_directories(tmp_path)
    process_repository = make_process_repository(tmp_path)
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    tracker_run = run_tracker_event(
        tracked_file, SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert tracker_run.returncode == 0

    dispatcher_run = run_bash_dispatcher(
        "git commit -m update",
        SESSION_ID,
        repository_root,
        temp_directory,
        home_directory,
        process_directory=process_repository,
    )
    assert dispatcher_run.returncode == 0
    decision, reason = parse_dispatcher_decision(dispatcher_run.stdout)
    assert decision == "deny"
    assert "widget.py" in reason


@pytest.mark.parametrize(
    "bash_command",
    [
        "cd child && git commit -m update",
        "pushd child && git commit -m update",
        "git -C child commit -m update",
    ],
)
def test_dispatcher_anchors_relative_command_directory_to_event_cwd(
    tmp_path: Path,
    bash_command: str,
) -> None:
    """Relative commit directories resolve from event cwd across command forms."""
    repository_root, temp_directory, home_directory = make_test_directories(tmp_path)
    process_repository = make_process_repository(tmp_path)
    prepare_process_child_repository(process_repository)
    (repository_root / "child").mkdir()
    tracked_file = prepare_repository_with_unstaged_edit(repository_root)
    tracker_run = run_tracker_event(
        tracked_file, SESSION_ID, repository_root, temp_directory, home_directory
    )
    assert tracker_run.returncode == 0

    dispatcher_run = run_bash_dispatcher(
        bash_command,
        SESSION_ID,
        repository_root,
        temp_directory,
        home_directory,
        process_directory=process_repository,
    )
    assert dispatcher_run.returncode == 0
    decision, reason = parse_dispatcher_decision(dispatcher_run.stdout)
    assert decision == "deny"
    assert "widget.py" in reason
