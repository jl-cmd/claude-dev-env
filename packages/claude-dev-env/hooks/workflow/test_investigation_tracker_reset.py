"""Behavior tests for investigation tracker reset."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
from unittest import mock

import pytest


HOOK_DIRECTORY = Path(__file__).parent
HOOK_SPEC = importlib.util.spec_from_file_location(
    "investigation_tracker_reset",
    HOOK_DIRECTORY / "investigation_tracker_reset.py",
)
assert HOOK_SPEC is not None
assert HOOK_SPEC.loader is not None
HOOK_MODULE = importlib.util.module_from_spec(HOOK_SPEC)
HOOK_SPEC.loader.exec_module(HOOK_MODULE)


def _run_main(input_text: str) -> None:
    with (
        mock.patch("sys.stdin", io.StringIO(input_text)),
        contextlib.suppress(SystemExit),
    ):
        HOOK_MODULE.main()


@pytest.mark.parametrize("delegation_tool", ["Agent", "Task", "TeamCreate"])
def test_main_removes_tracker_after_delegation(
    tmp_path: Path,
    delegation_tool: str,
) -> None:
    tracker_path = tmp_path / "investigation-tracker.json"
    tracker_path.write_text("{}", encoding="utf-8")
    HOOK_MODULE.__dict__["TRACKER_STATE_PATH"] = str(tracker_path)

    _run_main(json.dumps({"tool_name": delegation_tool}))

    assert not tracker_path.exists()


@pytest.mark.parametrize("unrelated_tool", ["Read", "Bash", "Grep"])
def test_main_keeps_tracker_for_unrelated_tool(
    tmp_path: Path,
    unrelated_tool: str,
) -> None:
    tracker_path = tmp_path / "investigation-tracker.json"
    tracker_path.write_text("{}", encoding="utf-8")
    HOOK_MODULE.__dict__["TRACKER_STATE_PATH"] = str(tracker_path)

    _run_main(json.dumps({"tool_name": unrelated_tool}))

    assert tracker_path.exists()


@pytest.mark.parametrize("invalid_input", ["not json", json.dumps([])])
def test_main_ignores_invalid_input(
    tmp_path: Path,
    invalid_input: str,
) -> None:
    tracker_path = tmp_path / "investigation-tracker.json"
    tracker_path.write_text("{}", encoding="utf-8")
    HOOK_MODULE.__dict__["TRACKER_STATE_PATH"] = str(tracker_path)

    _run_main(invalid_input)

    assert tracker_path.exists()


def test_main_keeps_running_when_tracker_removal_fails(tmp_path: Path) -> None:
    tracker_path = tmp_path / "investigation-tracker.json"
    tracker_path.write_text("{}", encoding="utf-8")
    HOOK_MODULE.__dict__["TRACKER_STATE_PATH"] = str(tracker_path)

    with mock.patch.object(HOOK_MODULE.os, "remove", side_effect=OSError("locked")):
        _run_main(json.dumps({"tool_name": "Agent"}))

    assert tracker_path.exists()
