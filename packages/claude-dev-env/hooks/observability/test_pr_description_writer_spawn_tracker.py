"""Unit tests for the pr-description-writer spawn tracker PostToolUse hook."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

_OBSERVABILITY_DIRECTORY = Path(__file__).resolve().parent
_HOOKS_DIRECTORY = _OBSERVABILITY_DIRECTORY.parent
for each_directory in (_OBSERVABILITY_DIRECTORY, _HOOKS_DIRECTORY):
    if str(each_directory) not in sys.path:
        sys.path.insert(0, str(each_directory))

_TRACKER_SPEC = importlib.util.spec_from_file_location(
    "pr_description_writer_spawn_tracker",
    _OBSERVABILITY_DIRECTORY / "pr_description_writer_spawn_tracker.py",
)
assert _TRACKER_SPEC is not None
assert _TRACKER_SPEC.loader is not None
tracker_module = importlib.util.module_from_spec(_TRACKER_SPEC)
_TRACKER_SPEC.loader.exec_module(tracker_module)

_SESSION_ID = "session-abc123"
_OTHER_SUBAGENT_TYPE = "general-purpose"


def _spawn_payload(
    subagent_type: str,
    tool_name: str = "Agent",
    session_id: str = _SESSION_ID,
) -> dict[str, object]:
    """Build a PostToolUse payload for one agent spawn.

    Args:
        subagent_type: The agent type the spawn names.
        tool_name: The spawning tool name.
        session_id: The session the spawn belongs to.

    Returns:
        The payload dictionary the tracker reads from stdin.
    """
    return {
        "tool_name": tool_name,
        "session_id": session_id,
        "tool_input": {
            "subagent_type": subagent_type,
            "description": "Write the PR body",
            "prompt": "Write a PR description from the diff.",
        },
    }


def _run_tracker(payload: dict[str, object], temp_directory: Path) -> None:
    """Run the tracker's main against a payload with temp redirected.

    Args:
        payload: The PostToolUse payload to feed on stdin.
        temp_directory: The directory standing in for the system temp root.
    """
    with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
        with mock.patch.object(
            tracker_module.tempfile, "gettempdir", return_value=str(temp_directory)
        ):
            tracker_module.main()


def should_record_marker_when_pr_description_writer_spawns(tmp_path: Path) -> None:
    """A pr-description-writer spawn leaves this session's marker on disk."""
    _run_tracker(_spawn_payload(tracker_module.PR_DESCRIPTION_WRITER_SUBAGENT_TYPE), tmp_path)
    assert tracker_module.spawn_marker_path(_SESSION_ID, tmp_path).exists() is True


def should_leave_no_marker_when_another_agent_spawns(tmp_path: Path) -> None:
    """A spawn of a different agent type records nothing."""
    _run_tracker(_spawn_payload(_OTHER_SUBAGENT_TYPE), tmp_path)
    assert tracker_module.spawn_marker_path(_SESSION_ID, tmp_path).exists() is False


@pytest.mark.parametrize("spawn_tool_name", ["Agent", "Task"])
def should_record_marker_for_each_spawn_tool_name(spawn_tool_name: str, tmp_path: Path) -> None:
    """Both spawning tool names record the marker."""
    payload = _spawn_payload(
        tracker_module.PR_DESCRIPTION_WRITER_SUBAGENT_TYPE, tool_name=spawn_tool_name
    )
    _run_tracker(payload, tmp_path)
    assert tracker_module.spawn_marker_path(_SESSION_ID, tmp_path).exists() is True


def should_leave_no_marker_for_an_unrelated_tool(tmp_path: Path) -> None:
    """A tool that is not a spawn records nothing, even naming the agent."""
    payload = _spawn_payload(tracker_module.PR_DESCRIPTION_WRITER_SUBAGENT_TYPE, tool_name="Bash")
    _run_tracker(payload, tmp_path)
    assert tracker_module.spawn_marker_path(_SESSION_ID, tmp_path).exists() is False


def should_keep_each_session_marker_separate(tmp_path: Path) -> None:
    """A spawn in one session leaves another session's marker absent."""
    payload = _spawn_payload(
        tracker_module.PR_DESCRIPTION_WRITER_SUBAGENT_TYPE, session_id="session-one"
    )
    _run_tracker(payload, tmp_path)
    assert tracker_module.spawn_marker_path("session-one", tmp_path).exists() is True
    assert tracker_module.spawn_marker_path("session-two", tmp_path).exists() is False


def should_record_twice_without_error(tmp_path: Path) -> None:
    """A second spawn in one session leaves the marker in place."""
    payload = _spawn_payload(tracker_module.PR_DESCRIPTION_WRITER_SUBAGENT_TYPE)
    _run_tracker(payload, tmp_path)
    _run_tracker(payload, tmp_path)
    assert tracker_module.spawn_marker_path(_SESSION_ID, tmp_path).exists() is True


def should_ignore_a_malformed_payload(tmp_path: Path) -> None:
    """Unparseable stdin records nothing and raises nothing."""
    with mock.patch("sys.stdin", io.StringIO("this is not json")):
        with mock.patch.object(tracker_module.tempfile, "gettempdir", return_value=str(tmp_path)):
            tracker_module.main()
    assert list(tmp_path.iterdir()) == []


def should_ignore_a_payload_with_no_tool_input(tmp_path: Path) -> None:
    """A spawn payload missing tool_input records nothing."""
    payload: dict[str, object] = {"tool_name": "Agent", "session_id": _SESSION_ID}
    _run_tracker(payload, tmp_path)
    assert tracker_module.spawn_marker_path(_SESSION_ID, tmp_path).exists() is False


@pytest.mark.parametrize("unusable_session_id", ["", "///"])
def should_record_nothing_without_a_usable_session_id(
    unusable_session_id: str, tmp_path: Path
) -> None:
    """A payload naming no usable session records no marker at all."""
    payload = _spawn_payload(
        tracker_module.PR_DESCRIPTION_WRITER_SUBAGENT_TYPE,
        session_id=unusable_session_id,
    )
    _run_tracker(payload, tmp_path)
    assert tracker_module.spawn_marker_path(unusable_session_id, tmp_path) is None
    assert list(tmp_path.iterdir()) == []
