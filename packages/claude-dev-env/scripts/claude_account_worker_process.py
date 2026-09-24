"""Launch a headless Claude worker process and wait for it to finish."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from dev_env_scripts_constants.claude_account_worker_constants import (
    DRAIN_ATTEMPT_LIMIT,
    DRAIN_GRACE_TIMEOUT_SECONDS,
    LAUNCH_FAILURE_EXIT_CODE,
    SECONDS_PER_MINUTE,
    TIMEOUT_EXIT_CODE,
    UTF8_DECODE_ERRORS,
    UTF8_ENCODING,
)
from shared_tree_paths import resolve_shared_process_tree_scripts_directory
from subprocess_stream_text import decode_stream_text
from subprocess_window_access import hidden_window_creation_flags

_process_tree_scripts_directory = resolve_shared_process_tree_scripts_directory(
    __file__, all_environment=os.environ
)
if str(_process_tree_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_process_tree_scripts_directory))

_process_tree_kill = importlib.import_module("process_tree_kill")
_should_start_new_session = _process_tree_kill.should_start_new_session


class WorkerProcess(Protocol):
    returncode: int | None

    pid: int

    def communicate(
        self,
        input: str | None = None,
        timeout: float | None = None,
    ) -> tuple[str | bytes | None, str | bytes | None]: ...

    def poll(self) -> int | None: ...

    def kill(self) -> None: ...


def _decoded_text(stream_payload: str | bytes | None) -> str:
    return decode_stream_text(
        stream_payload, encoding=UTF8_ENCODING, errors=UTF8_DECODE_ERRORS
    )


def _launch_process(
    process_factory: Callable[..., WorkerProcess],
    all_arguments: list[str],
    cwd: Path,
    all_child_environment_variables: dict[str, str],
) -> WorkerProcess | None:
    try:
        return process_factory(
            all_arguments,
            cwd=str(cwd),
            env=all_child_environment_variables,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=UTF8_ENCODING,
            errors=UTF8_DECODE_ERRORS,
            start_new_session=_should_start_new_session(),
            creationflags=hidden_window_creation_flags(),
        )
    except OSError:
        return None


def _drain_attempt_outcome(process: WorkerProcess) -> tuple[bool, str]:
    try:
        captured_stdout, _ = process.communicate(timeout=DRAIN_GRACE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as timeout_error:
        return False, _decoded_text(timeout_error.output)
    return True, _decoded_text(captured_stdout)


def _drain_after_termination(
    process: WorkerProcess,
    process_terminator: Callable[[WorkerProcess], None],
    initial_stdout_text: str,
) -> str:
    latest_stdout_text = initial_stdout_text
    for _ in range(DRAIN_ATTEMPT_LIMIT):
        process_terminator(process)
        did_drain, attempt_stdout_text = _drain_attempt_outcome(process)
        if attempt_stdout_text:
            latest_stdout_text = attempt_stdout_text
        if did_drain:
            return latest_stdout_text
    return latest_stdout_text


class ProcessControls(Protocol):
    """The process factory, terminator, and clock a worker run uses."""

    process_factory: Callable[..., WorkerProcess]
    process_terminator: Callable[[WorkerProcess], None]
    monotonic_clock: Callable[[], float]


def _await_completion(
    process: WorkerProcess | None,
    prompt_text: str,
    timeout_minutes: int,
    process_terminator: Callable[[WorkerProcess], None],
) -> tuple[int, str]:
    if process is None:
        return LAUNCH_FAILURE_EXIT_CODE, ""
    try:
        captured_stdout, _ = process.communicate(
            input=prompt_text,
            timeout=timeout_minutes * SECONDS_PER_MINUTE,
        )
    except subprocess.TimeoutExpired as timeout_error:
        stdout_text = _drain_after_termination(
            process, process_terminator, _decoded_text(timeout_error.output)
        )
        return TIMEOUT_EXIT_CODE, stdout_text
    process_exit_code = (
        process.returncode
        if process.returncode is not None
        else LAUNCH_FAILURE_EXIT_CODE
    )
    return process_exit_code, _decoded_text(captured_stdout)


def invoke_worker(
    *,
    all_arguments: list[str],
    cwd: Path,
    all_child_environment_variables: dict[str, str],
    prompt_text: str,
    timeout_minutes: int,
    controls: ProcessControls,
) -> tuple[int, float, str]:
    """Launch the worker process and return its exit code, duration, and stdout.

    Args:
        all_arguments: The full command line, executable first.
        cwd: Working directory the child process runs in.
        all_child_environment_variables: Environment passed to the child.
        prompt_text: The prompt piped to the child on stdin.
        timeout_minutes: Minutes to wait before the child is timed out.
        controls: The process factory, terminator, and clock.

    Returns:
        The exit code, the duration in seconds, and the decoded stdout.
    """
    process_start = controls.monotonic_clock()
    process = _launch_process(
        controls.process_factory, all_arguments, cwd, all_child_environment_variables
    )
    exit_code, stdout_text = _await_completion(
        process, prompt_text, timeout_minutes, controls.process_terminator
    )
    return exit_code, controls.monotonic_clock() - process_start, stdout_text
