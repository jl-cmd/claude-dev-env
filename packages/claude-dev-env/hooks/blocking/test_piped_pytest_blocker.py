"""Tests for the piped-pytest Bash blocker.

The deny cases each carry a pytest spelling whose output feeds a pipe; the allow
cases each carry a pytest or pipe shape that keeps the pytest exit code. The
dispatcher case drives the payload through the hosted-hook chain, so it holds
only while the roster carries the segment.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

_BLOCKING_DIR = Path(__file__).resolve().parent
_HOOKS_DIR = str(_BLOCKING_DIR.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
_BLOCKING_DIR_TEXT = str(_BLOCKING_DIR)
if _BLOCKING_DIR_TEXT not in sys.path:
    sys.path.insert(0, _BLOCKING_DIR_TEXT)

from hooks_constants.piped_pytest_blocker_constants import (  # noqa: E402
    CORRECTIVE_MESSAGE,
)
from hooks_constants.shell_command_segments import split_into_segments  # noqa: E402
from piped_pytest_blocker import (  # noqa: E402
    find_piped_pytest_violation,
    segment_runs_pytest,
)

SCRIPT_PATH = _BLOCKING_DIR / "piped_pytest_blocker.py"
DISPATCHER_PATH = _BLOCKING_DIR / "bash_pre_tool_use_dispatcher.py"
QUOTED_PIPE_COMMAND = 'pytest -k "a|b"'
SHARED_SPLITTER_SEGMENTS_FOR_QUOTED_PIPE = [["pytest", "-k", "a"], ["b"]]

ALL_PIPED_PYTEST_COMMANDS = [
    "pytest tests | tee run.log",
    "python -m pytest tests | head -50",
    r"C:\Python313\python.exe -m pytest tests | tee run.log",
    "python -m pytest tests 2>&1 | tee run.log",
    "cd packages/claude-dev-env && pytest | cat",
]

ALL_EXIT_CODE_PRESERVING_COMMANDS = [
    "pytest tests",
    "python -m pytest tests > run.log 2>&1",
    "git status --short | head -20",
    "cat ids.txt | pytest --stdin",
    "pytest tests && echo done | tee run.log",
    "python -m mypy . | tee types.log",
]


def _run_process(script_path: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def _bash_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _deny_reason_from_stdout(stdout_text: str) -> str:
    parsed_payload = json.loads(stdout_text)
    hook_specific = parsed_payload["hookSpecificOutput"]
    assert hook_specific["permissionDecision"] == "deny"
    return hook_specific["permissionDecisionReason"]


@pytest.mark.parametrize("each_command", ALL_PIPED_PYTEST_COMMANDS)
def test_denies_a_pytest_run_feeding_a_pipe(each_command: str) -> None:
    """Each covered pytest spelling returns the deny message when it feeds a pipe."""
    assert find_piped_pytest_violation(each_command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize("each_command", ALL_EXIT_CODE_PRESERVING_COMMANDS)
def test_allows_a_command_that_keeps_the_pytest_exit_code(each_command: str) -> None:
    """Bare pytest, redirection-only pytest, and unrelated pipes stay allowed."""
    assert find_piped_pytest_violation(each_command) is None


def test_quoted_pipe_reads_as_unpiped_here_and_as_a_cut_by_the_shared_splitter() -> None:
    """One input, both readings: this hook allows it, the shared splitter cuts it.

    The shared splitter's segments for the input are pinned, so a quote-aware
    ``shell_command_segments`` turns this test red — the signal to move this
    module onto the shared helper.
    """
    assert find_piped_pytest_violation(QUOTED_PIPE_COMMAND) is None
    assert (
        split_into_segments(shlex.split(QUOTED_PIPE_COMMAND))
        == SHARED_SPLITTER_SEGMENTS_FOR_QUOTED_PIPE
    )


def test_segment_leading_with_pytest_is_recognized() -> None:
    """A segment whose program is pytest reads as a pytest run."""
    assert segment_runs_pytest(["pytest", "tests", "-q"]) is True


def test_segment_running_another_python_module_is_not_pytest() -> None:
    """An interpreter running a different module reads as no pytest run."""
    assert segment_runs_pytest(["python", "-m", "mypy", "."]) is False


def test_hook_emits_a_deny_payload_for_a_piped_pytest_run() -> None:
    """The standalone hook writes the deny message for a piped pytest command."""
    completed = _run_process(SCRIPT_PATH, _bash_payload("pytest tests | tee run.log"))
    assert _deny_reason_from_stdout(completed.stdout) == CORRECTIVE_MESSAGE


def test_deny_message_names_running_pytest_alone_and_the_exit_code() -> None:
    """The deny message states the fix and why the pipe hides a failure."""
    completed = _run_process(SCRIPT_PATH, _bash_payload("pytest | tee run.log"))
    deny_reason = _deny_reason_from_stdout(completed.stdout)
    assert "run pytest alone" in deny_reason.lower()
    assert "exit code" in deny_reason.lower()


def test_hook_stays_silent_on_a_bare_pytest_run() -> None:
    """A pytest command with no pipe produces no decision."""
    completed = _run_process(SCRIPT_PATH, _bash_payload("pytest tests"))
    assert completed.stdout == ""


def test_ignores_an_unsupported_tool_name() -> None:
    """A non-Bash tool payload produces no decision."""
    payload = {"tool_name": "Edit", "tool_input": {"command": "pytest | tee run.log"}}
    assert _run_process(SCRIPT_PATH, payload).stdout == ""


def test_ignores_a_payload_without_a_command() -> None:
    """A Bash payload carrying no command produces no decision."""
    assert _run_process(SCRIPT_PATH, {"tool_name": "Bash", "tool_input": {}}).stdout == ""


def test_dispatcher_denies_a_piped_pytest_run() -> None:
    """The hosted-hook chain surfaces the deny, so the roster carries the segment."""
    completed = _run_process(DISPATCHER_PATH, _bash_payload("pytest tests | tee run.log"))
    assert "exit code" in _deny_reason_from_stdout(completed.stdout).lower()
