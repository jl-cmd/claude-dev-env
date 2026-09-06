from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import cast

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from pr_verification import lock as lock_module
from pr_verification.lock import SupervisorLock, SupervisorLockError

LOCK_CONTENDER_SCRIPT = """
import sys
import time
from pathlib import Path

scripts_directory = Path(sys.argv[1])
cache_root = Path(sys.argv[2])
result_path = Path(sys.argv[3])
start_path = Path(sys.argv[4])
sys.path.insert(0, str(scripts_directory))

from pr_verification.lock import SupervisorLock, SupervisorLockError

while not start_path.exists():
    time.sleep(0.01)

try:
    with SupervisorLock(cache_root):
        result_path.write_text("acquired", encoding="utf-8")
        while True:
            time.sleep(1)
except SupervisorLockError:
    result_path.write_text("contended", encoding="utf-8")
"""
RESULT_WAIT_SECONDS = 5
PROCESS_WAIT_SECONDS = 10
POLL_INTERVAL_SECONDS = 0.01
LEGACY_LOCK_CONTENT = "legacy owner metadata"
BASE_PYTHON_EXECUTABLE = cast(str, getattr(sys, "_base_executable", sys.executable))


def _start_lock_contender(
    cache_root: Path, result_path: Path, start_path: Path
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            BASE_PYTHON_EXECUTABLE,
            "-c",
            LOCK_CONTENDER_SCRIPT,
            str(SCRIPTS_DIRECTORY),
            str(cache_root),
            str(result_path),
            str(start_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_lock_outcomes(all_result_paths: list[Path]) -> list[str]:
    deadline = time.monotonic() + RESULT_WAIT_SECONDS
    while time.monotonic() < deadline:
        if all(each_path.is_file() for each_path in all_result_paths):
            return [
                each_path.read_text(encoding="utf-8") for each_path in all_result_paths
            ]
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError("lock contenders did not report within five seconds")


def _terminate_owned_child(child_process: subprocess.Popen[str]) -> None:
    if child_process.poll() is None:
        child_process.terminate()
    child_process.wait(timeout=PROCESS_WAIT_SECONDS)


def _start_simultaneous_lock_contenders(
    cache_root: Path, all_result_paths: list[Path], start_path: Path
) -> list[subprocess.Popen[str]]:
    all_child_processes = [
        _start_lock_contender(cache_root, each_result_path, start_path)
        for each_result_path in all_result_paths
    ]
    start_path.touch()
    return all_child_processes


def _stop_initial_lock_processes(
    all_child_processes: list[subprocess.Popen[str]], all_outcomes: list[str]
) -> None:
    contender_index = all_outcomes.index("contended")
    all_child_processes[contender_index].wait(timeout=PROCESS_WAIT_SECONDS)
    owner_index = all_outcomes.index("acquired")
    _terminate_owned_child(all_child_processes[owner_index])


def test_second_supervisor_cannot_own_same_cache_root(tmp_path: Path) -> None:
    first_lock = SupervisorLock(tmp_path)
    second_lock = SupervisorLock(tmp_path)

    with first_lock, pytest.raises(SupervisorLockError):
        second_lock.acquire()


def test_process_lock_survives_contention_and_owner_termination(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "supervisor.lock"
    lock_path.write_text(LEGACY_LOCK_CONTENT, encoding="utf-8")
    start_path = tmp_path / "start"
    all_result_paths = [tmp_path / "first.result", tmp_path / "second.result"]
    all_child_processes = _start_simultaneous_lock_contenders(
        tmp_path, all_result_paths, start_path
    )
    try:
        all_outcomes = _wait_for_lock_outcomes(all_result_paths)
        assert sorted(all_outcomes) == ["acquired", "contended"]
        _stop_initial_lock_processes(all_child_processes, all_outcomes)

        recovery_result_path = tmp_path / "recovery.result"
        recovery_process = _start_lock_contender(
            tmp_path, recovery_result_path, start_path
        )
        all_child_processes.append(recovery_process)
        assert _wait_for_lock_outcomes([recovery_result_path]) == ["acquired"]
        assert lock_path.is_file()
        _terminate_owned_child(recovery_process)
        assert lock_path.read_text(encoding="utf-8") == LEGACY_LOCK_CONTENT
    finally:
        for each_child_process in all_child_processes:
            _terminate_owned_child(each_child_process)


def test_lock_io_error_is_presented_as_supervisor_lock_error(
    tmp_path: Path,
) -> None:
    (tmp_path / "supervisor.lock").mkdir()

    with pytest.raises(
        SupervisorLockError,
        match="Verification supervisor lock file is unavailable",
    ) as raised_error:
        SupervisorLock(tmp_path).acquire()

    assert isinstance(raised_error.value.__cause__, OSError)


def test_contention_error_survives_a_failing_descriptor_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def close_fails(file_descriptor: int) -> None:
        raise OSError("close failed")

    first_lock = SupervisorLock(tmp_path)
    with first_lock:
        monkeypatch.setattr(lock_module.os, "close", close_fails)
        with pytest.raises(SupervisorLockError) as raised:
            SupervisorLock(tmp_path).acquire()
        monkeypatch.undo()
    assert str(raised.value) == lock_module.SUPERVISOR_LOCK_ERROR
