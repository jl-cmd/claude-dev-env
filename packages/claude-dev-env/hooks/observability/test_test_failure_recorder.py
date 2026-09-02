"""Behavior tests for the test_failure_recorder PostToolUse hook.

Drives the hook's main through real stdin payloads shaped like a genuine
Bash PostToolUse call, then reads the shared content-hash store back to
confirm what -- if anything -- it recorded. The store's real state file
under the OS temp directory is read directly, the same way
test_content_hash_store.py and test_tdd_enforcer.py already do, rather than
mocking tempfile.gettempdir. ``hooks/conftest.py`` already puts the hooks
and blocking directories on sys.path for test collection, so this file needs
no bootstrap of its own before importing content_hash_store.
"""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
from unittest import mock

from tdd_enforcer_parts import content_hash_store

_HOOK_DIRECTORY = Path(__file__).parent
_hook_spec = importlib.util.spec_from_file_location(
    "test_failure_recorder_under_test", _HOOK_DIRECTORY / "test_failure_recorder.py"
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)


def _run_hook_with_payload(payload: dict) -> None:
    with (
        mock.patch("sys.stdin", io.StringIO(json.dumps(payload))),
        contextlib.suppress(SystemExit),
    ):
        _hook_module.main()


def _recorded_failure_entry(test_file: Path, session_id: str, repository_root: str) -> dict | None:
    state_file = content_hash_store._state_file_path(session_id, repository_root)
    if not state_file.exists():
        return None
    state = json.loads(state_file.read_text())
    return state.get(content_hash_store._state_key_for(test_file))


def _bash_payload(command: str, tool_response: object, cwd: Path, session_id: str) -> dict:
    return {
        "session_id": session_id,
        "cwd": str(cwd),
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": tool_response,
    }


_FAILING_OUTPUT = (
    "Error: Exit code 1\n"
    "F                                                                    [100%]\n"
    "=================================== FAILURES ===================================\n"
    "FAILED test_orders.py::test_fulfill - AssertionError\n"
    "1 failed in 0.02s"
)
_PASSING_OUTPUT = {"stdout": "1 passed in 0.02s", "stderr": "", "interrupted": False}


def test_records_a_failure_for_a_bare_pytest_command_naming_a_real_file(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_fulfill(): assert False\n")
    session_id = "recorder-session-1"

    _run_hook_with_payload(
        _bash_payload("pytest test_orders.py", _FAILING_OUTPUT, tmp_path, session_id)
    )

    entry = _recorded_failure_entry(test_file, session_id, str(tmp_path))
    assert entry is not None
    assert entry[content_hash_store.STORED_FAILURE_EXIT_STATUS_KEY] == 1
    assert entry[content_hash_store.STORED_FAILURE_COMMAND_KEY] == "pytest test_orders.py"


def test_does_not_record_for_a_passing_command(tmp_path: Path) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_fulfill(): pass\n")
    session_id = "recorder-session-2"

    _run_hook_with_payload(
        _bash_payload("pytest test_orders.py", _PASSING_OUTPUT, tmp_path, session_id)
    )

    assert _recorded_failure_entry(test_file, session_id, str(tmp_path)) is None


def test_does_not_record_for_a_non_pytest_command(tmp_path: Path) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_fulfill(): assert False\n")
    session_id = "recorder-session-3"

    _run_hook_with_payload(
        _bash_payload("npm test", "Error: Exit code 1\n1 failing", tmp_path, session_id)
    )

    assert _recorded_failure_entry(test_file, session_id, str(tmp_path)) is None


def test_does_not_record_for_a_chained_command(tmp_path: Path) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_fulfill(): assert False\n")
    session_id = "recorder-session-4"

    _run_hook_with_payload(
        _bash_payload("cd /repo && pytest test_orders.py", _FAILING_OUTPUT, tmp_path, session_id)
    )

    assert _recorded_failure_entry(test_file, session_id, str(tmp_path)) is None


def test_does_not_record_for_a_bare_pytest_run_with_no_path_argument(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_fulfill(): assert False\n")
    session_id = "recorder-session-5"

    _run_hook_with_payload(_bash_payload("pytest -q", _FAILING_OUTPUT, tmp_path, session_id))

    assert _recorded_failure_entry(test_file, session_id, str(tmp_path)) is None


def test_records_only_the_named_file_not_an_option_or_expression_token(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_fulfill(): assert False\n")
    session_id = "recorder-session-6"

    _run_hook_with_payload(
        _bash_payload("pytest test_orders.py -k fulfill", _FAILING_OUTPUT, tmp_path, session_id)
    )

    entry = _recorded_failure_entry(test_file, session_id, str(tmp_path))
    assert entry is not None
    state_file = content_hash_store._state_file_path(session_id, str(tmp_path))
    state = json.loads(state_file.read_text())
    assert len(state) == 1


def test_ignores_a_tool_other_than_bash(tmp_path: Path) -> None:
    test_file = tmp_path / "test_orders.py"
    test_file.write_text("def test_fulfill(): assert False\n")
    session_id = "recorder-session-7"
    payload = _bash_payload("pytest test_orders.py", _FAILING_OUTPUT, tmp_path, session_id)
    payload["tool_name"] = "Write"

    _run_hook_with_payload(payload)

    assert _recorded_failure_entry(test_file, session_id, str(tmp_path)) is None


def test_does_not_record_when_the_named_file_does_not_exist_on_disk(
    tmp_path: Path,
) -> None:
    session_id = "recorder-session-8"
    missing_file = tmp_path / "test_missing.py"

    _run_hook_with_payload(
        _bash_payload("pytest test_missing.py", _FAILING_OUTPUT, tmp_path, session_id)
    )

    assert _recorded_failure_entry(missing_file, session_id, str(tmp_path)) is None
