"""Behavior tests for the session_file_edit_tracker PostToolUse hook.

The tracker records the resolved absolute file path of every Write, Edit, and
MultiEdit into a per-session JSON file under the system temp directory. These
tests drive the hook's ``main`` through real stdin payloads with
``tempfile.gettempdir`` redirected to a temporary directory, then read the
JSON file back to confirm what was recorded.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import threading
import time
from typing import Any
from unittest import mock

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_TREE = _HOOK_DIR.parent
for each_path in (str(_HOOK_DIR), str(_HOOKS_TREE)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

hook_spec = importlib.util.spec_from_file_location(
    "session_file_edit_tracker",
    _HOOK_DIR / "session_file_edit_tracker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    ALL_EDITED_FILE_PATHS_KEY,
    SESSION_EDIT_FILE_PREFIX,
    SESSION_EDIT_FILE_SUFFIX,
)

_SESSION_ID = "sessionabc123"
_CONCURRENT_EDIT_COUNT = 5
_CONCURRENT_READ_DELAY_SECONDS = 0.05


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


def _edit_file_path(temp_directory: pathlib.Path, session_id: str) -> pathlib.Path:
    return temp_directory / f"{SESSION_EDIT_FILE_PREFIX}{session_id}{SESSION_EDIT_FILE_SUFFIX}"


def _read_recorded_paths(temp_directory: pathlib.Path, session_id: str) -> list[str]:
    edit_file = _edit_file_path(temp_directory, session_id)
    parsed = json.loads(edit_file.read_text(encoding="utf-8"))
    return parsed[ALL_EDITED_FILE_PATHS_KEY]


def _write_payload(tool_name: str, file_path: pathlib.Path, session_id: str) -> str:
    payload: dict[str, Any] = {
        "session_id": session_id,
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
    }
    return json.dumps(payload)


def test_should_record_write_tool_edit(redirected_temp_directory: pathlib.Path) -> None:
    edited_file = redirected_temp_directory / "module_under_edit.py"
    _run_main_with_stdin(_write_payload("Write", edited_file, _SESSION_ID))
    recorded = _read_recorded_paths(redirected_temp_directory, _SESSION_ID)
    assert str(edited_file.resolve()) in recorded


def test_should_record_edit_tool_edit(redirected_temp_directory: pathlib.Path) -> None:
    edited_file = redirected_temp_directory / "module_under_edit.py"
    _run_main_with_stdin(_write_payload("Edit", edited_file, _SESSION_ID))
    recorded = _read_recorded_paths(redirected_temp_directory, _SESSION_ID)
    assert str(edited_file.resolve()) in recorded


def test_should_record_multiedit_tool_edit(redirected_temp_directory: pathlib.Path) -> None:
    edited_file = redirected_temp_directory / "module_under_edit.py"
    _run_main_with_stdin(_write_payload("MultiEdit", edited_file, _SESSION_ID))
    recorded = _read_recorded_paths(redirected_temp_directory, _SESSION_ID)
    assert str(edited_file.resolve()) in recorded


def test_should_ignore_bash_tool(redirected_temp_directory: pathlib.Path) -> None:
    bash_payload = json.dumps(
        {
            "session_id": _SESSION_ID,
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
        }
    )
    _run_main_with_stdin(bash_payload)
    assert not _edit_file_path(redirected_temp_directory, _SESSION_ID).exists()


def test_should_deduplicate_repeated_paths(redirected_temp_directory: pathlib.Path) -> None:
    edited_file = redirected_temp_directory / "module_under_edit.py"
    _run_main_with_stdin(_write_payload("Write", edited_file, _SESSION_ID))
    _run_main_with_stdin(_write_payload("Edit", edited_file, _SESSION_ID))
    recorded = _read_recorded_paths(redirected_temp_directory, _SESSION_ID)
    assert recorded.count(str(edited_file.resolve())) == 1


def test_should_sanitize_unsafe_session_id_in_filename(
    redirected_temp_directory: pathlib.Path,
) -> None:
    unsafe_session_id = "a/../b c"
    edited_file = redirected_temp_directory / "module_under_edit.py"
    _run_main_with_stdin(_write_payload("Write", edited_file, unsafe_session_id))
    sanitized_file = _edit_file_path(redirected_temp_directory, "abc")
    assert sanitized_file.exists()


def test_should_record_every_path_under_concurrent_edits(
    redirected_temp_directory: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    concurrent_session_id = "concurrentsession"
    real_read_recorded_paths = hook_module._read_recorded_paths

    def slow_read_recorded_paths(edit_file: pathlib.Path) -> list[str]:
        recorded_before_delay = real_read_recorded_paths(edit_file)
        time.sleep(_CONCURRENT_READ_DELAY_SECONDS)
        return recorded_before_delay

    monkeypatch.setattr(hook_module, "_read_recorded_paths", slow_read_recorded_paths)
    all_edited_paths = [
        str((redirected_temp_directory / f"module_{each_index}.py").resolve())
        for each_index in range(_CONCURRENT_EDIT_COUNT)
    ]
    all_threads = [
        threading.Thread(
            target=hook_module._record_edited_path,
            args=(concurrent_session_id, each_path),
        )
        for each_path in all_edited_paths
    ]
    for each_thread in all_threads:
        each_thread.start()
    for each_thread in all_threads:
        each_thread.join()
    recorded = _read_recorded_paths(redirected_temp_directory, concurrent_session_id)
    assert sorted(recorded) == sorted(all_edited_paths)


def test_should_exit_zero_on_malformed_stdin(
    redirected_temp_directory: pathlib.Path,
) -> None:
    _run_main_with_stdin("not valid json {{{")
    assert not any(redirected_temp_directory.iterdir())
