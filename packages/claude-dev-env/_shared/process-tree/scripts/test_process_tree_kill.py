"""Behavioral tests for the shared process-tree kill helper.

Every test drives ``process_tree_kill`` itself: the platform branch it picks,
the taskkill argv it builds, the failures it swallows, and the
``Popen.kill()`` fallback it reaches when a tree kill leaves the child alive.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import process_tree_kill  # noqa: E402
from process_tree_kill import (  # noqa: E402
    kill_process_tree_by_identifier,
    terminate_process_tree,
)
from process_tree_scripts_constants.process_tree_kill_constants import (  # noqa: E402
    PROCESS_TREE_KILL_TIMEOUT_SECONDS,
    WINDOWS_TASKKILL_COMMAND,
    WINDOWS_TASKKILL_FORCE_FLAG,
    WINDOWS_TASKKILL_PID_FLAG,
    WINDOWS_TASKKILL_TREE_FLAG,
)

FAKE_PROCESS_IDENTIFIER = 4242
FAKE_PROCESS_GROUP_IDENTIFIER = 909
WINDOWS_PLATFORM = "win32"
POSIX_PLATFORM = "linux"
FAKE_KILL_SIGNAL = 9


class _FakeProcess:
    """Stands in for ``subprocess.Popen`` with a scripted liveness sequence.

    ``poll()`` returns each queued answer in turn, so a test names exactly what
    the helper sees before the tree kill and after it.
    """

    def __init__(
        self,
        all_poll_results: list[int | None],
        *,
        kill_error: BaseException | None = None,
    ) -> None:
        self.pid = FAKE_PROCESS_IDENTIFIER
        self._all_poll_results = list(all_poll_results)
        self._kill_error = kill_error
        self.kill_calls = 0

    def poll(self) -> int | None:
        if not self._all_poll_results:
            return None
        return self._all_poll_results.pop(0)

    def kill(self) -> None:
        self.kill_calls += 1
        if self._kill_error is not None:
            raise self._kill_error


class _TreeKillRecorder:
    """Stands in for ``subprocess.run`` so no real taskkill leaves the test."""

    def __init__(self, raised_error: BaseException | None = None) -> None:
        self.all_invocations: list[list[str]] = []
        self.all_keyword_arguments: list[dict[str, object]] = []
        self._raised_error = raised_error

    def __call__(
        self, invocation: list[str], **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        self.all_invocations.append(list(invocation))
        self.all_keyword_arguments.append(dict(keyword_arguments))
        if self._raised_error is not None:
            raise self._raised_error
        return subprocess.CompletedProcess(args=invocation, returncode=0)


def _install_windows_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_tree_kill.sys, "platform", WINDOWS_PLATFORM)


def _install_posix_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_tree_kill.sys, "platform", POSIX_PLATFORM)
    monkeypatch.setattr(
        process_tree_kill.signal, "SIGKILL", FAKE_KILL_SIGNAL, raising=False
    )


def test_windows_tree_kill_issues_the_taskkill_tree_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Windows branch runs ``taskkill /T /F /PID <pid>`` under its timeout."""
    tree_kill_recorder = _TreeKillRecorder()
    _install_windows_platform(monkeypatch)
    monkeypatch.setattr(
        process_tree_kill, "process_tree_subprocess_run", tree_kill_recorder
    )

    kill_process_tree_by_identifier(FAKE_PROCESS_IDENTIFIER)

    assert tree_kill_recorder.all_invocations == [
        [
            WINDOWS_TASKKILL_COMMAND,
            WINDOWS_TASKKILL_TREE_FLAG,
            WINDOWS_TASKKILL_FORCE_FLAG,
            WINDOWS_TASKKILL_PID_FLAG,
            str(FAKE_PROCESS_IDENTIFIER),
        ]
    ]
    assert (
        tree_kill_recorder.all_keyword_arguments[0].get("timeout")
        == PROCESS_TREE_KILL_TIMEOUT_SECONDS
    )


@pytest.mark.parametrize(
    "raised_error",
    [
        subprocess.TimeoutExpired(
            cmd=[WINDOWS_TASKKILL_COMMAND], timeout=PROCESS_TREE_KILL_TIMEOUT_SECONDS
        ),
        OSError("taskkill is not on PATH"),
    ],
    ids=["taskkill_times_out", "taskkill_cannot_launch"],
)
def test_windows_tree_kill_swallows_a_failing_taskkill(
    monkeypatch: pytest.MonkeyPatch, raised_error: BaseException
) -> None:
    """A taskkill that hangs or cannot launch leaves the caller free to fall back."""
    _install_windows_platform(monkeypatch)
    monkeypatch.setattr(
        process_tree_kill,
        "process_tree_subprocess_run",
        _TreeKillRecorder(raised_error),
    )

    kill_process_tree_by_identifier(FAKE_PROCESS_IDENTIFIER)


def test_posix_tree_kill_signals_the_whole_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The POSIX branch resolves the child's group and signals the group, not the pid."""
    all_group_signals: list[tuple[int, int]] = []
    _install_posix_platform(monkeypatch)
    monkeypatch.setattr(
        process_tree_kill.os,
        "getpgid",
        lambda process_identifier: FAKE_PROCESS_GROUP_IDENTIFIER,
        raising=False,
    )
    monkeypatch.setattr(
        process_tree_kill.os,
        "killpg",
        lambda group_identifier, signal_number: all_group_signals.append(
            (group_identifier, signal_number)
        ),
        raising=False,
    )

    kill_process_tree_by_identifier(FAKE_PROCESS_IDENTIFIER)

    assert all_group_signals == [(FAKE_PROCESS_GROUP_IDENTIFIER, FAKE_KILL_SIGNAL)]


def test_posix_tree_kill_swallows_an_already_reaped_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pid already reaped raises OSError; the caller still gets its fallback."""

    def raise_no_such_process(process_identifier: int) -> int:
        del process_identifier
        raise ProcessLookupError("no such process")

    _install_posix_platform(monkeypatch)
    monkeypatch.setattr(
        process_tree_kill.os, "getpgid", raise_no_such_process, raising=False
    )

    kill_process_tree_by_identifier(FAKE_PROCESS_IDENTIFIER)


def test_terminate_skips_a_process_that_already_exited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exited process needs no kill, so neither the tree kill nor kill() runs."""
    tree_kill_recorder = _TreeKillRecorder()
    _install_windows_platform(monkeypatch)
    monkeypatch.setattr(
        process_tree_kill, "process_tree_subprocess_run", tree_kill_recorder
    )
    exited_process = _FakeProcess([0])

    terminate_process_tree(exited_process)  # type: ignore[arg-type]

    assert tree_kill_recorder.all_invocations == []
    assert exited_process.kill_calls == 0


def test_terminate_stops_after_a_tree_kill_that_took(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tree kill that ends the child leaves no work for the kill() fallback."""
    _install_windows_platform(monkeypatch)
    monkeypatch.setattr(
        process_tree_kill, "process_tree_subprocess_run", _TreeKillRecorder()
    )
    killed_process = _FakeProcess([None, 0])

    terminate_process_tree(killed_process)  # type: ignore[arg-type]

    assert killed_process.kill_calls == 0


def test_terminate_falls_back_to_direct_kill_when_the_tree_kill_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child alive after the tree kill is killed directly, so no caller waits on it.

    ::

        taskkill raises, child still polls None  ok:   Popen.kill() runs
        no fallback                              flag: Popen.__exit__ waits forever
    """
    _install_windows_platform(monkeypatch)
    monkeypatch.setattr(
        process_tree_kill,
        "process_tree_subprocess_run",
        _TreeKillRecorder(OSError("taskkill is not on PATH")),
    )
    surviving_process = _FakeProcess([None, None])

    terminate_process_tree(surviving_process)  # type: ignore[arg-type]

    assert surviving_process.kill_calls == 1


def test_terminate_swallows_a_kill_on_a_process_that_just_exited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child that exits between the re-poll and the kill raises; the helper returns."""
    _install_windows_platform(monkeypatch)
    monkeypatch.setattr(
        process_tree_kill, "process_tree_subprocess_run", _TreeKillRecorder()
    )
    racing_process = _FakeProcess(
        [None, None], kill_error=ProcessLookupError("no such process")
    )

    terminate_process_tree(racing_process)  # type: ignore[arg-type]

    assert racing_process.kill_calls == 1


def test_new_session_is_requested_off_windows_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A POSIX child gets its own session so ``killpg`` never reaches the parent.

    ::

        posix    ok:   start_new_session True, child leads its own group
        windows  flag: start_new_session unsupported, so False
    """
    _install_posix_platform(monkeypatch)
    assert process_tree_kill.should_start_new_session() is True

    _install_windows_platform(monkeypatch)
    assert process_tree_kill.should_start_new_session() is False
