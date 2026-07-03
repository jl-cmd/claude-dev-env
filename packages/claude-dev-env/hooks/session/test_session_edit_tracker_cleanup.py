"""Behavior tests for the session_edit_tracker_cleanup hook.

The cleanup deletes only the running session's own session-edit file, and only
on a fresh startup (SessionStart with a ``startup`` source) or a session end. A
SessionStart that continues the same conversation — a compact or a resume —
keeps the in-flight tracker. A peer session's file is always left alone,
regardless of its age. These tests redirect ``tempfile.gettempdir`` to a
temporary directory, seed it with the current session's file and peer-session
files, run the hook's ``main`` through a lifecycle payload, and confirm which
files survive.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import time
from unittest import mock

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_TREE = _HOOK_DIR.parent
for each_path in (str(_HOOK_DIR), str(_HOOKS_TREE)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

hook_spec = importlib.util.spec_from_file_location(
    "session_edit_tracker_cleanup",
    _HOOK_DIR / "session_edit_tracker_cleanup.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    ALL_EDITED_FILE_PATHS_KEY,
    SESSION_EDIT_FILE_PREFIX,
    SESSION_EDIT_FILE_STALE_AGE_SECONDS,
    SESSION_EDIT_FILE_SUFFIX,
)


def _run_main_with_stdin(input_text: str) -> None:
    with (
        mock.patch("sys.stdin", io.StringIO(input_text)),
        mock.patch("sys.stdout", new_callable=io.StringIO),
        contextlib.suppress(SystemExit),
    ):
        hook_module.main()


@pytest.fixture()
def redirected_temp_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    return tmp_path


def _seed_edit_file(temp_directory: pathlib.Path, session_id: str) -> pathlib.Path:
    edit_file = temp_directory / f"{SESSION_EDIT_FILE_PREFIX}{session_id}{SESSION_EDIT_FILE_SUFFIX}"
    edit_file.write_text(json.dumps({ALL_EDITED_FILE_PATHS_KEY: []}), encoding="utf-8")
    return edit_file


def _age_file(target_file: pathlib.Path, age_seconds: float) -> None:
    old_time = time.time() - age_seconds
    os.utime(target_file, (old_time, old_time))


def _session_start_payload(session_id: str) -> str:
    return json.dumps({"session_id": session_id, "source": "startup"})


def _session_continuation_payload(session_id: str, source: str) -> str:
    return json.dumps({"session_id": session_id, "source": source})


def _session_end_payload(session_id: str) -> str:
    return json.dumps({"session_id": session_id, "hook_event_name": "SessionEnd"})


def test_main_keeps_other_session_stale_tracker(
    redirected_temp_directory: pathlib.Path,
) -> None:
    other_session_file = _seed_edit_file(redirected_temp_directory, "idle-live-session")
    _age_file(other_session_file, SESSION_EDIT_FILE_STALE_AGE_SECONDS + 60)
    _run_main_with_stdin(_session_start_payload("currentsession"))
    assert other_session_file.exists()


def test_should_keep_fresh_edit_file(redirected_temp_directory: pathlib.Path) -> None:
    fresh_file = _seed_edit_file(redirected_temp_directory, "other-live-session")
    _run_main_with_stdin(_session_start_payload("currentsession"))
    assert fresh_file.exists()


def test_should_remove_current_session_edit_file(
    redirected_temp_directory: pathlib.Path,
) -> None:
    current_file = _seed_edit_file(redirected_temp_directory, "currentsession")
    _run_main_with_stdin(_session_start_payload("currentsession"))
    assert not current_file.exists()


def test_main_removes_current_session_stale_tracker(
    redirected_temp_directory: pathlib.Path,
) -> None:
    current_file = _seed_edit_file(redirected_temp_directory, "currentsession")
    _age_file(current_file, SESSION_EDIT_FILE_STALE_AGE_SECONDS + 60)
    _run_main_with_stdin(_session_start_payload("currentsession"))
    assert not current_file.exists()


@pytest.mark.parametrize("continuation_source", ["compact", "resume"])
def test_should_keep_current_session_tracker_on_continuation(
    redirected_temp_directory: pathlib.Path, continuation_source: str
) -> None:
    current_file = _seed_edit_file(redirected_temp_directory, "currentsession")
    _run_main_with_stdin(
        _session_continuation_payload("currentsession", continuation_source)
    )
    assert current_file.exists()


def test_should_remove_current_session_tracker_on_session_end(
    redirected_temp_directory: pathlib.Path,
) -> None:
    current_file = _seed_edit_file(redirected_temp_directory, "currentsession")
    _run_main_with_stdin(_session_end_payload("currentsession"))
    assert not current_file.exists()


def test_should_exit_zero_on_malformed_stdin(
    redirected_temp_directory: pathlib.Path,
) -> None:
    fresh_file = _seed_edit_file(redirected_temp_directory, "other-live-session")
    _run_main_with_stdin("not valid json {{{")
    assert fresh_file.exists()
