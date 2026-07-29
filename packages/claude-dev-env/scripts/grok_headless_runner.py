#!/usr/bin/env python3
"""Run one worker role as a headless grok process and classify the outcome.

Builds a headless argv, mints a unique ``--leader-socket`` path under the
caller-supplied run state directory, captures stdout/stderr/returncode, kills
the process tree on timeout, and classifies failures via signature lists in
``dev_env_scripts_constants.grok_worker_constants``.

The timeout is the only bound on a worker's length; the argv carries no turn
cap.

Dual-match policy matches preflight: when both usage and auth signatures appear
in the same streams, auth wins (``CLASSIFICATION_AUTH_FAILURE``).

Import ``run_headless_worker`` for the outcome object::

    outcome = run_headless_worker(
        prompt_file=path,
        working_directory=cwd,
        run_state_directory=run_dir,
        timeout_seconds=5400,
        agent_name="code-quality-agent",
    )
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

_shared_process_tree_scripts_directory = (
    Path(__file__).resolve().parents[1] / "_shared" / "process-tree" / "scripts"
)
if str(_shared_process_tree_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_shared_process_tree_scripts_directory))

from process_tree_kill import (  # noqa: E402
    should_start_new_session,
    terminate_process_tree,
)

from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    AGENT_FLAG,
    ALL_AUTH_FAILURE_SIGNATURES,
    ALL_USAGE_LIMIT_SIGNATURES,
    ALWAYS_APPROVE_FLAG,
    CLASSIFICATION_AUTH_FAILURE,
    CLASSIFICATION_ERROR,
    CLASSIFICATION_KILL_FAILED,
    CLASSIFICATION_OK,
    CLASSIFICATION_STREAM_JOIN_SEPARATOR,
    CLASSIFICATION_TIMEOUT,
    CLASSIFICATION_USAGE_LIMIT,
    CWD_FLAG,
    GROK_BINARY_NAME,
    GROK_BINARY_NOT_FOUND_STDERR,
    GROK_MODEL_PIN,
    KILL_FAILED_RETURN_CODE,
    KILL_FAILED_STDERR_TEMPLATE,
    KILL_GRACE_TIMEOUT_SECONDS,
    LAUNCH_FAILURE_RETURN_CODE,
    LAUNCH_FAILURE_STDERR_PREFIX,
    LEADER_SOCKET_FILENAME_PREFIX,
    LEADER_SOCKET_FILENAME_SUFFIX,
    LEADER_SOCKET_FLAG,
    MAXIMUM_WORKER_TIMEOUT_ERROR_TEMPLATE,
    MAXIMUM_WORKER_TIMEOUT_SECONDS,
    MIN_WORKER_TIMEOUT_SECONDS,
    MINIMUM_WORKER_TIMEOUT_ERROR_TEMPLATE,
    MISSING_BINARY_RETURN_CODE,
    MODEL_FLAG,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    PROCESS_TREE_KILL_ATTEMPT_LIMIT,
    PROMPT_FILE_FLAG,
    TIMEOUT_RETURN_CODE,
    UTF8_DECODE_ERRORS,
    UTF8_ENCODING,
    WORKER_SPEC_TIMEOUT_KEY,
)

runner_popen = subprocess.Popen


class WorkerTimeoutOutOfBoundsError(ValueError):
    """Raised when a requested worker timeout falls outside the accepted bounds.

    A ``ValueError`` subclass so existing callers that catch ``ValueError``
    keep working, while a caller that wants only this fault can name it.
    """


@dataclass(frozen=True)
class GrokRunnerOutcome:
    """Outcome of one headless grok worker invocation.

    ``classification`` is one of the ``CLASSIFICATION_*`` constants from
    ``grok_worker_constants``.
    """

    is_ok: bool
    returncode: int
    classification: str
    stdout: str
    stderr: str


def _mint_leader_socket_path(run_state_directory: Path) -> Path:
    unique_token = uuid.uuid4().hex
    socket_filename = (
        f"{LEADER_SOCKET_FILENAME_PREFIX}{unique_token}{LEADER_SOCKET_FILENAME_SUFFIX}"
    )
    return run_state_directory / socket_filename


def _build_invocation(
    *,
    prompt_file: Path,
    working_directory: Path,
    leader_socket_path: Path,
    agent_name: str | None,
    all_extra_arguments: tuple[str, ...] = (),
) -> list[str]:
    all_arguments = [
        GROK_BINARY_NAME,
        PROMPT_FILE_FLAG,
        str(prompt_file),
        CWD_FLAG,
        str(working_directory),
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        ALWAYS_APPROVE_FLAG,
        LEADER_SOCKET_FLAG,
        str(leader_socket_path),
    ]
    if agent_name:
        all_arguments.extend([AGENT_FLAG, agent_name])
    if GROK_MODEL_PIN:
        all_arguments.extend([MODEL_FLAG, GROK_MODEL_PIN])
    all_arguments.extend(all_extra_arguments)
    return all_arguments


def _combined_text(stdout_text: str, stderr_text: str) -> str:
    return CLASSIFICATION_STREAM_JOIN_SEPARATOR.join(
        (stdout_text, stderr_text)
    ).lower()


def _matches_any_signature(combined_text: str, all_signatures: tuple[str, ...]) -> bool:
    return any(each_signature in combined_text for each_signature in all_signatures)


def _classify_completion(
    returncode: int, stdout_text: str, stderr_text: str
) -> GrokRunnerOutcome:
    if returncode == 0:
        return GrokRunnerOutcome(
            is_ok=True,
            returncode=returncode,
            classification=CLASSIFICATION_OK,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    combined_text = _combined_text(stdout_text, stderr_text)
    is_usage_limit = _matches_any_signature(combined_text, ALL_USAGE_LIMIT_SIGNATURES)
    is_auth_failure = _matches_any_signature(combined_text, ALL_AUTH_FAILURE_SIGNATURES)
    if is_usage_limit and not is_auth_failure:
        return GrokRunnerOutcome(
            is_ok=False,
            returncode=returncode,
            classification=CLASSIFICATION_USAGE_LIMIT,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    if is_auth_failure:
        return GrokRunnerOutcome(
            is_ok=False,
            returncode=returncode,
            classification=CLASSIFICATION_AUTH_FAILURE,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    return GrokRunnerOutcome(
        is_ok=False,
        returncode=returncode,
        classification=CLASSIFICATION_ERROR,
        stdout=stdout_text,
        stderr=stderr_text,
    )


def _normalize_stream(stream_payload: str | bytes | None) -> str:
    if stream_payload is None:
        return ""
    if isinstance(stream_payload, bytes):
        return stream_payload.decode(UTF8_ENCODING, errors=UTF8_DECODE_ERRORS)
    return stream_payload


def _resolve_returncode(process: subprocess.Popen[str]) -> int:
    if process.returncode is not None:
        return process.returncode
    return TIMEOUT_RETURN_CODE


def require_timeout_within_bounds(timeout_seconds: int | None) -> None:
    """Refuse a timeout that is missing, below the floor, or above the ceiling.

    ::

        None or 0  flag: ValueError naming MIN_WORKER_TIMEOUT_SECONDS
        5401       flag: ValueError naming MAXIMUM_WORKER_TIMEOUT_SECONDS
        1 .. 5400  ok:   returns

    Public so a dispatcher can apply the same bounds on a path that never
    reaches ``run_headless_worker``.

    Args:
        timeout_seconds: The requested per-worker timeout in seconds.

    Raises:
        WorkerTimeoutOutOfBoundsError: When the value falls outside the bounds.
    """
    if timeout_seconds is None or timeout_seconds < MIN_WORKER_TIMEOUT_SECONDS:
        raise WorkerTimeoutOutOfBoundsError(
            MINIMUM_WORKER_TIMEOUT_ERROR_TEMPLATE.format(
                field_name=WORKER_SPEC_TIMEOUT_KEY,
                requested_seconds=timeout_seconds,
                minimum_seconds=MIN_WORKER_TIMEOUT_SECONDS,
            )
        )
    if timeout_seconds > MAXIMUM_WORKER_TIMEOUT_SECONDS:
        raise WorkerTimeoutOutOfBoundsError(
            MAXIMUM_WORKER_TIMEOUT_ERROR_TEMPLATE.format(
                field_name=WORKER_SPEC_TIMEOUT_KEY,
                requested_seconds=timeout_seconds,
                maximum_seconds=MAXIMUM_WORKER_TIMEOUT_SECONDS,
            )
        )


def _drain_after_kill(process: subprocess.Popen[str]) -> tuple[str, str] | None:
    """Read the killed process's streams, or None when the grace window expires."""
    try:
        return process.communicate(timeout=KILL_GRACE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return None


def _kill_and_drain_within_attempt_limit(
    process: subprocess.Popen[str],
) -> tuple[str, str] | None:
    """Kill the process tree and drain it, retrying up to the attempt limit.

    ::

        attempt 1 drains         ok:   streams, one attempt made
        attempt 1 times out,
        attempt 2 drains         ok:   streams, two attempts made
        every attempt times out  flag: None

    A tree kill that returns without taking leaves the drain waiting on a live
    pipe, so a timed-out drain is followed by another kill-and-drain round.
    ``terminate_process_tree`` re-issues the kill only while the worker
    process is still alive; once it has exited, the next round is a second
    drain window for the descendants still holding the pipe open.

    Args:
        process: The timed-out worker process to kill and read.

    Returns:
        The captured stdout and stderr, or None when every attempt timed out.
    """
    attempts_made = 0
    while attempts_made < PROCESS_TREE_KILL_ATTEMPT_LIMIT:
        terminate_process_tree(process)
        all_captured_streams = _drain_after_kill(process)
        if all_captured_streams is not None:
            return all_captured_streams
        attempts_made += 1
    return None


def _kill_failed_outcome(process: subprocess.Popen[str]) -> GrokRunnerOutcome:
    diagnostic_text = KILL_FAILED_STDERR_TEMPLATE.format(
        attempt_count=PROCESS_TREE_KILL_ATTEMPT_LIMIT,
        process_identifier=process.pid,
    )
    return GrokRunnerOutcome(
        is_ok=False,
        returncode=KILL_FAILED_RETURN_CODE,
        classification=CLASSIFICATION_KILL_FAILED,
        stdout="",
        stderr=diagnostic_text,
    )


def _timeout_outcome(process: subprocess.Popen[str]) -> GrokRunnerOutcome:
    """Kill a timed-out worker's tree, then classify what the kill achieved.

    ::

        drain clears on attempt 1 or 2  ok:   classification timeout
        both attempts leave it draining flag: classification kill_failed
    """
    all_captured_streams = _kill_and_drain_within_attempt_limit(process)
    if all_captured_streams is None:
        return _kill_failed_outcome(process)
    captured_stdout, captured_stderr = all_captured_streams
    stdout_text = _normalize_stream(captured_stdout)
    stderr_text = _normalize_stream(captured_stderr)
    returncode = _resolve_returncode(process)
    if returncode == 0:
        return _classify_completion(returncode, stdout_text, stderr_text)
    return GrokRunnerOutcome(
        is_ok=False,
        returncode=returncode,
        classification=CLASSIFICATION_TIMEOUT,
        stdout=stdout_text,
        stderr=stderr_text,
    )


def _missing_binary_outcome() -> GrokRunnerOutcome:
    return GrokRunnerOutcome(
        is_ok=False,
        returncode=MISSING_BINARY_RETURN_CODE,
        classification=CLASSIFICATION_ERROR,
        stdout="",
        stderr=GROK_BINARY_NOT_FOUND_STDERR,
    )


def _launch_failure_outcome(launch_error: OSError) -> GrokRunnerOutcome:
    diagnostic_text = f"{LAUNCH_FAILURE_STDERR_PREFIX}{launch_error}"
    return GrokRunnerOutcome(
        is_ok=False,
        returncode=LAUNCH_FAILURE_RETURN_CODE,
        classification=CLASSIFICATION_ERROR,
        stdout="",
        stderr=diagnostic_text,
    )


def _invoke_process(
    all_arguments: list[str], *, timeout_seconds: int
) -> GrokRunnerOutcome:
    try:
        process = runner_popen(
            all_arguments,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=UTF8_ENCODING,
            errors=UTF8_DECODE_ERRORS,
            start_new_session=should_start_new_session(),
        )
    except FileNotFoundError:
        return _missing_binary_outcome()
    except OSError as launch_error:
        return _launch_failure_outcome(launch_error)
    try:
        captured_stdout, captured_stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return _timeout_outcome(process)
    stdout_text = _normalize_stream(captured_stdout)
    stderr_text = _normalize_stream(captured_stderr)
    returncode = _resolve_returncode(process)
    return _classify_completion(returncode, stdout_text, stderr_text)


def run_headless_worker(
    *,
    prompt_file: Path,
    working_directory: Path,
    run_state_directory: Path,
    timeout_seconds: int,
    agent_name: str | None = None,
    leader_socket_path: Path | None = None,
    all_extra_arguments: tuple[str, ...] = (),
) -> GrokRunnerOutcome:
    """Run one headless grok worker and classify the process outcome.

    The timeout is the worker's only bound; the argv carries no turn cap.

    Args:
        prompt_file: Path to the prompt file passed via ``--prompt-file``.
        working_directory: Working directory passed via ``--cwd``.
        run_state_directory: Run-scoped directory the leader socket is minted
            under. Read only when ``leader_socket_path`` is omitted.
        timeout_seconds: Seconds before the process tree is killed on expiry.
            Must sit between ``MIN_WORKER_TIMEOUT_SECONDS`` and
            ``MAXIMUM_WORKER_TIMEOUT_SECONDS`` inclusive.
        agent_name: Optional role agent name passed via ``--agent``.
        leader_socket_path: Optional pre-minted leader socket path. When omitted,
            a unique path is minted under ``run_state_directory``.
        all_extra_arguments: Extra CLI tokens appended after the base argv
            (tool-profile flags, debug file, and similar).

    Returns:
        The classified outcome including return code and captured streams.

    Raises:
        WorkerTimeoutOutOfBoundsError: When ``timeout_seconds`` is missing,
            below the floor, or above the ceiling.
    """
    require_timeout_within_bounds(timeout_seconds)
    resolved_leader_socket_path = (
        leader_socket_path
        if leader_socket_path is not None
        else _mint_leader_socket_path(run_state_directory)
    )
    all_arguments = _build_invocation(
        prompt_file=prompt_file,
        working_directory=working_directory,
        leader_socket_path=resolved_leader_socket_path,
        agent_name=agent_name,
        all_extra_arguments=all_extra_arguments,
    )
    return _invoke_process(all_arguments, timeout_seconds=timeout_seconds)
