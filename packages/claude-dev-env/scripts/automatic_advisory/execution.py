from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from .config.constants import (
    CHILD_BASE_FLAG,
    CHILD_EXECUTOR_FLAG,
    CHILD_OUTPUT_FLAG,
    LOCAL_VERIFICATION_CLI_FILENAME,
    PYTEST_AUTO_WORKERS_ENVIRONMENT_KEY,
    PYTEST_AUTO_WORKERS_LIMIT,
    PYTHON_MODULE_ARGUMENT,
    PYTHONPATH_ENVIRONMENT_KEY,
    SCOPED_VERIFICATION_SCRIPT_PATH,
    WINDOWS_PLATFORM,
    WINDOWS_PRIORITY_CLASS_ATTRIBUTE,
    WINDOWS_PROCESS_HOST_MODULE,
    WINDOWS_PROCESS_START_SIGNAL,
)
from .config.timing import CHILD_CLEANUP_TIMEOUT_SECONDS
from .model import AdvisoryRegistration, ChildOutcome
from .windows_job import (
    _assign_process,
    _close_handle,
    _create_kill_on_close_job,
    _terminate_job,
)


@dataclass(frozen=True)
class OwnedChildProcess:
    process: subprocess.Popen[str]
    process_group_identifier: int | None
    windows_job_handle: int | None


def run_verification_child(
    registration: AdvisoryRegistration,
    base_ref: str,
    timeout_seconds: float,
) -> ChildOutcome:
    """Run the existing local verification CLI with a bounded timeout.

    Args:
        registration: Checkout, manifest, and report paths for the pair.
        base_ref: Dedicated fetched base revision.
        timeout_seconds: Maximum child runtime.

    Returns:
        Captured child status and streams.
    """
    scripts_directory = Path(__file__).resolve().parents[1]
    all_arguments = _build_child_arguments(registration, base_ref, scripts_directory)
    child_environment = _build_child_environment(registration, scripts_directory)
    if not _clear_child_artifacts(registration):
        return ChildOutcome(None, "", "child artifacts could not be cleared", False)
    maybe_owned_child = _start_child_process(
        all_arguments, registration, child_environment
    )
    if maybe_owned_child is None:
        return ChildOutcome(None, "", "child process could not start", False)
    return _collect_child_outcome(maybe_owned_child, timeout_seconds)


def _build_child_arguments(
    registration: AdvisoryRegistration,
    base_ref: str,
    scripts_directory: Path,
) -> tuple[str, ...]:
    verification_cli_path = (
        scripts_directory / "local_verification" / LOCAL_VERIFICATION_CLI_FILENAME
    )
    return (
        sys.executable,
        str(registration.checkout_path / SCOPED_VERIFICATION_SCRIPT_PATH),
        CHILD_BASE_FLAG,
        base_ref,
        CHILD_EXECUTOR_FLAG,
        str(verification_cli_path),
        CHILD_OUTPUT_FLAG,
        str(registration.report_path),
    )


def _build_child_environment(
    registration: AdvisoryRegistration, scripts_directory: Path
) -> dict[str, str]:
    child_environment = os.environ.copy()
    all_python_paths = [str(registration.checkout_path), str(scripts_directory)]
    existing_python_path = child_environment.get(PYTHONPATH_ENVIRONMENT_KEY)
    if existing_python_path:
        all_python_paths.append(existing_python_path)
    child_environment[PYTHONPATH_ENVIRONMENT_KEY] = os.pathsep.join(all_python_paths)
    child_environment[PYTEST_AUTO_WORKERS_ENVIRONMENT_KEY] = PYTEST_AUTO_WORKERS_LIMIT
    return child_environment


def _clear_child_artifacts(registration: AdvisoryRegistration) -> bool:
    try:
        for each_artifact_path in (
            registration.report_path,
            registration.selected_manifest_path,
        ):
            each_artifact_path.unlink(missing_ok=True)
    except OSError:
        return False
    return True


def _child_produced_report(
    child_outcome: ChildOutcome,
    registration: AdvisoryRegistration,
) -> bool:
    if child_outcome.exit_code is None or child_outcome.timed_out:
        return False
    if not registration.selected_manifest_path.is_file():
        return False
    try:
        report_fields = json.loads(registration.report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(report_fields, dict)
        and report_fields.get("exit_code") == child_outcome.exit_code
    )


def _start_child_process(
    all_arguments: tuple[str, ...],
    registration: AdvisoryRegistration,
    all_child_environment: dict[str, str],
) -> OwnedChildProcess | None:
    if sys.platform == WINDOWS_PLATFORM:
        return _start_windows_child(
            all_arguments,
            registration,
            all_child_environment,
        )
    return _start_posix_child(
        all_arguments,
        registration,
        all_child_environment,
    )


def _start_posix_child(
    all_arguments: tuple[str, ...],
    registration: AdvisoryRegistration,
    all_child_environment: dict[str, str],
) -> OwnedChildProcess | None:
    try:
        child_process = subprocess.Popen(
            all_arguments,
            cwd=registration.checkout_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=all_child_environment,
            start_new_session=True,
        )
    except OSError:
        return None
    return OwnedChildProcess(child_process, child_process.pid, None)


def _start_windows_child(
    all_arguments: tuple[str, ...],
    registration: AdvisoryRegistration,
    all_child_environment: dict[str, str],
) -> OwnedChildProcess | None:
    maybe_job_handle = _create_kill_on_close_job()
    if maybe_job_handle is None:
        return None
    maybe_child_process = _spawn_windows_process_host(
        all_arguments,
        registration,
        all_child_environment,
    )
    if maybe_child_process is None:
        _close_handle(maybe_job_handle)
        return None
    if not _assign_process(maybe_job_handle, maybe_child_process.pid):
        _stop_unowned_process(maybe_child_process)
        _close_handle(maybe_job_handle)
        return None
    if not _release_windows_process_host(maybe_child_process):
        _terminate_job(maybe_job_handle)
        _close_handle(maybe_job_handle)
        return None
    return OwnedChildProcess(maybe_child_process, None, maybe_job_handle)


def _spawn_windows_process_host(
    all_arguments: tuple[str, ...],
    registration: AdvisoryRegistration,
    all_child_environment: dict[str, str],
) -> subprocess.Popen[str] | None:
    try:
        return subprocess.Popen(
            (
                sys.executable,
                PYTHON_MODULE_ARGUMENT,
                WINDOWS_PROCESS_HOST_MODULE,
                *all_arguments,
            ),
            cwd=registration.checkout_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=all_child_environment,
            creationflags=getattr(subprocess, WINDOWS_PRIORITY_CLASS_ATTRIBUTE, 0),
        )
    except OSError:
        return None


def _release_windows_process_host(child_process: subprocess.Popen[str]) -> bool:
    stdin_stream = child_process.stdin
    if stdin_stream is None:
        return False
    child_process.stdin = None
    try:
        stdin_stream.write(WINDOWS_PROCESS_START_SIGNAL)
        stdin_stream.flush()
        return True
    except OSError:
        return False
    finally:
        _close_stream_without_raising(stdin_stream)


def _close_stream_without_raising(stream: IO[str]) -> None:
    try:
        stream.close()
    except OSError:
        return


def _collect_child_outcome(
    owned_child: OwnedChildProcess,
    timeout_seconds: float,
) -> ChildOutcome:
    child_process = owned_child.process
    try:
        try:
            stdout_text, stderr_text = child_process.communicate(
                timeout=timeout_seconds
            )
        except subprocess.TimeoutExpired as timeout_error:
            return _stop_timed_out_child(owned_child, timeout_error)
        return ChildOutcome(
            child_process.returncode,
            stdout_text,
            stderr_text,
            False,
        )
    finally:
        _close_process_ownership(owned_child)
        _close_child_streams(child_process)
        _reap_child_process(child_process)


def _stop_timed_out_child(
    owned_child: OwnedChildProcess,
    timeout_error: subprocess.TimeoutExpired,
) -> ChildOutcome:
    child_process = owned_child.process
    _terminate_owned_process_tree(owned_child)
    try:
        stdout_text, stderr_text = child_process.communicate(
            timeout=CHILD_CLEANUP_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as cleanup_error:
        stdout_text = str(cleanup_error.stdout or timeout_error.stdout or "")
        stderr_text = str(cleanup_error.stderr or timeout_error.stderr or "")
    return ChildOutcome(None, str(stdout_text), str(stderr_text), True)


def _terminate_owned_process_tree(
    owned_child: OwnedChildProcess,
) -> None:
    if owned_child.windows_job_handle is not None:
        _terminate_job(owned_child.windows_job_handle)
    if owned_child.process_group_identifier is not None:
        _kill_posix_process_group(owned_child.process_group_identifier)
    _kill_direct_child(owned_child.process)


def _kill_posix_process_group(process_group_identifier: int) -> None:
    if sys.platform == "win32":
        return
    try:
        os.killpg(process_group_identifier, signal.SIGKILL)
    except OSError:
        return


def _kill_direct_child(child_process: subprocess.Popen[str]) -> None:
    if child_process.poll() is None:
        try:
            child_process.kill()
        except ProcessLookupError:
            pass


def _close_process_ownership(owned_child: OwnedChildProcess) -> None:
    if owned_child.windows_job_handle is None:
        return
    _close_handle(owned_child.windows_job_handle)


def _close_child_streams(child_process: subprocess.Popen[str]) -> None:
    for each_stream in (
        child_process.stdout,
        child_process.stderr,
        child_process.stdin,
    ):
        if each_stream is None:
            continue
        try:
            each_stream.close()
        except OSError:
            pass


def _stop_unowned_process(child_process: subprocess.Popen[str]) -> None:
    try:
        child_process.kill()
    except ProcessLookupError:
        return
    _reap_child_process(child_process)


def _reap_child_process(child_process: subprocess.Popen[str]) -> None:
    if child_process.poll() is not None:
        return
    try:
        child_process.wait(timeout=CHILD_CLEANUP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return
