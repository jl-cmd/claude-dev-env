#!/usr/bin/env python3
"""Run one worker role as a headless grok process and classify the outcome.

Builds a headless argv, mints a unique ``--leader-socket`` path under the
caller-supplied run state directory, captures stdout/stderr/returncode, kills
the process on timeout, and classifies failures via signature lists in
``dev_env_scripts_constants.grok_worker_constants``.

Import ``run_headless_worker`` for the outcome object::

    outcome = run_headless_worker(
        prompt_file=path,
        working_directory=cwd,
        run_state_directory=run_dir,
        max_turns=8,
        timeout_seconds=600,
        agent_name="code-quality-agent",
    )
"""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from dev_env_scripts_constants.grok_worker_constants import (
    AGENT_FLAG,
    ALL_AUTH_FAILURE_SIGNATURES,
    ALL_USAGE_LIMIT_SIGNATURES,
    ALWAYS_APPROVE_FLAG,
    CLASSIFICATION_AUTH_FAILURE,
    CLASSIFICATION_ERROR,
    CLASSIFICATION_OK,
    CLASSIFICATION_TIMEOUT,
    CLASSIFICATION_USAGE_LIMIT,
    CWD_FLAG,
    GROK_BINARY_NAME,
    GROK_MODEL_PIN,
    KILL_GRACE_TIMEOUT_SECONDS,
    LAUNCH_FAILURE_RETURN_CODE,
    LAUNCH_FAILURE_STDERR_PREFIX,
    LEADER_SOCKET_FILENAME_PREFIX,
    LEADER_SOCKET_FILENAME_SUFFIX,
    LEADER_SOCKET_FLAG,
    MAX_TURNS_FLAG,
    MODEL_FLAG,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    PROMPT_FILE_FLAG,
    TIMEOUT_RETURN_CODE,
    UTF8_DECODE_ERRORS,
    UTF8_ENCODING,
)

runner_popen = subprocess.Popen


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
    max_turns: int,
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
        MAX_TURNS_FLAG,
        str(max_turns),
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
    return f"{stdout_text}{stderr_text}".lower()


def _matches_any_signature(
    combined_text: str, all_signatures: tuple[str, ...]
) -> bool:
    return any(
        each_signature in combined_text for each_signature in all_signatures
    )


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
    is_usage_limit = _matches_any_signature(
        combined_text, ALL_USAGE_LIMIT_SIGNATURES
    )
    is_auth_failure = _matches_any_signature(
        combined_text, ALL_AUTH_FAILURE_SIGNATURES
    )
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


def _normalize_stream(stream_payload: str | None) -> str:
    if stream_payload is None:
        return ""
    return stream_payload


def _resolve_returncode(process: subprocess.Popen[str]) -> int:
    if process.returncode is not None:
        return process.returncode
    return TIMEOUT_RETURN_CODE


def _timeout_outcome(process: subprocess.Popen[str]) -> GrokRunnerOutcome:
    process.kill()
    try:
        captured_stdout, captured_stderr = process.communicate(
            timeout=KILL_GRACE_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        captured_stdout, captured_stderr = "", ""
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
        )
    except OSError as launch_error:
        return _launch_failure_outcome(launch_error)
    try:
        captured_stdout, captured_stderr = process.communicate(
            timeout=timeout_seconds
        )
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
    max_turns: int,
    timeout_seconds: int,
    agent_name: str | None = None,
    leader_socket_path: Path | None = None,
    all_extra_arguments: tuple[str, ...] = (),
) -> GrokRunnerOutcome:
    """Run one headless grok worker and classify the process outcome.

    Args:
        prompt_file: Path to the prompt file passed via ``--prompt-file``.
        working_directory: Working directory passed via ``--cwd``.
        run_state_directory: Run-scoped directory the leader socket is minted
            under. Read only when ``leader_socket_path`` is omitted.
        max_turns: Maximum agent turns passed via ``--max-turns``.
        timeout_seconds: Seconds before the process is killed on expiry.
        agent_name: Optional role agent name passed via ``--agent``.
        leader_socket_path: Optional pre-minted leader socket path. When omitted,
            a unique path is minted under ``run_state_directory``.
        all_extra_arguments: Extra CLI tokens appended after the base argv
            (tool-profile flags, debug file, and similar).

    Returns:
        The classified outcome including return code and captured streams.
    """
    resolved_leader_socket_path = (
        leader_socket_path
        if leader_socket_path is not None
        else _mint_leader_socket_path(run_state_directory)
    )
    all_arguments = _build_invocation(
        prompt_file=prompt_file,
        working_directory=working_directory,
        max_turns=max_turns,
        leader_socket_path=resolved_leader_socket_path,
        agent_name=agent_name,
        all_extra_arguments=all_extra_arguments,
    )
    return _invoke_process(all_arguments, timeout_seconds=timeout_seconds)
