"""Headless wrapper that runs one Codex review and captures its outputs.

::

    review_outcome = run_codex_review(
        repository_directory=Path("/path/to/repo"),
        run_state_directory=Path("/path/to/run_state"),
        is_uncommitted=True,
    )
    review_outcome.outcome_class  # "completed" or "codex_down"
    review_outcome.jsonl_path     # path to captured JSONL stream
    review_outcome.agent_message  # final agent_message text
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from codex_review_scripts_constants.codex_usage_probe_constants import (
    ALL_WINDOWS_SCRIPT_SUFFIXES,
    WINDOWS_COMMAND_SHELL,
    WINDOWS_COMMAND_SHELL_RUN_FLAG,
    WINDOWS_OS_NAME,
    WINDOWS_TASKKILL_COMMAND,
    WINDOWS_TASKKILL_FORCE_FLAG,
    WINDOWS_TASKKILL_PID_FLAG,
    WINDOWS_TASKKILL_TREE_FLAG,
)
from codex_review_scripts_constants.run_constants import (
    ALL_SHAPE_PROBE_REQUIRED_FLAGS,
    BASE_TARGET_FLAG,
    CAPTURE_STREAMS_KEYWORD,
    CHECK_KEYWORD,
    CODEX_BINARY_NAME,
    CODEX_MODEL_PIN,
    COMMIT_TARGET_FLAG,
    CUSTOM_INSTRUCTIONS_PROMPT,
    CWD_KEYWORD,
    DEFAULT_TIMEOUT_SECONDS,
    ENCODING_KEYWORD,
    ENVIRONMENT_KEYWORD,
    EXEC_SUBCOMMAND,
    HELP_FLAG,
    JSON_FLAG,
    JSONL_AGENT_MESSAGE_TEXT_KEY,
    JSONL_AGENT_MESSAGE_TYPE,
    JSONL_CAPTURE_FILENAME,
    JSONL_CAPTURE_NEWLINE,
    JSONL_ENTRY_COMPLETED_TYPE,
    JSONL_ENTRY_KEY,
    JSONL_EVENT_TYPE_KEY,
    MISSING_BINARY_EXIT_CODE,
    MODEL_FLAG,
    OUTCOME_CLASS_CODEX_DOWN,
    OUTCOME_CLASS_COMPLETED,
    PROCESS_TREE_KILL_TIMEOUT_SECONDS,
    REVIEW_SUBCOMMAND,
    SHAPE_FLAG_TOKEN_TAIL_PATTERN,
    SUBPROCESS_DECODE_EXIT_CODE,
    TEXT_MODE_KEYWORD,
    TIMEOUT_EXIT_CODE,
    TIMEOUT_KEYWORD,
    UNCOMMITTED_TARGET_FLAG,
    UTF8_ENCODING,
    VERSION_FLAG,
    VERSION_PROBE_PATTERN,
)


def _kill_windows_process_tree(process_identifier: int) -> None:
    """Kill a Windows process and every descendant it started, by PID."""
    subprocess.run(
        [
            WINDOWS_TASKKILL_COMMAND,
            WINDOWS_TASKKILL_TREE_FLAG,
            WINDOWS_TASKKILL_FORCE_FLAG,
            WINDOWS_TASKKILL_PID_FLAG,
            str(process_identifier),
        ],
        capture_output=True,
        check=False,
        timeout=PROCESS_TREE_KILL_TIMEOUT_SECONDS,
    )


def _kill_posix_process_group(process_identifier: int) -> None:
    """Kill a POSIX process group so no grandchild keeps the capture pipe open."""
    if os.name == WINDOWS_OS_NAME:
        return
    try:
        process_group_identifier = os.getpgid(process_identifier)
        os.killpg(process_group_identifier, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return


def _terminate_process_tree(review_process: subprocess.Popen[str]) -> None:
    """Kill the review process and every descendant it spawned.

    Tree kill first (taskkill /T or killpg). When the direct child is still
    alive after that, fall back to ``Popen.kill()`` so ``Popen.__exit__`` never
    hits an unbounded wait on a surviving process.
    """
    if review_process.poll() is not None:
        return
    if os.name == WINDOWS_OS_NAME:
        _kill_windows_process_tree(review_process.pid)
    else:
        _kill_posix_process_group(review_process.pid)
    if review_process.poll() is not None:
        return
    try:
        review_process.kill()
    except ProcessLookupError:
        return


def _open_codex_popen(
    all_arguments: list[str],
    all_keyword_arguments: dict[str, object],
) -> subprocess.Popen[str]:
    """Start the codex process in its own session so its tree can be killed."""
    should_capture = bool(all_keyword_arguments.get(CAPTURE_STREAMS_KEYWORD, False))
    stream_target = subprocess.PIPE if should_capture else None
    working_directory = all_keyword_arguments.get(CWD_KEYWORD)
    stream_encoding = all_keyword_arguments.get(ENCODING_KEYWORD)
    process_environment = all_keyword_arguments.get(ENVIRONMENT_KEYWORD)
    return subprocess.Popen(
        all_arguments,
        cwd=working_directory if isinstance(working_directory, str) else None,
        stdout=stream_target,
        stderr=stream_target,
        text=bool(all_keyword_arguments.get(TEXT_MODE_KEYWORD, False)),
        encoding=stream_encoding if isinstance(stream_encoding, str) else None,
        env=process_environment if isinstance(process_environment, dict) else None,
        start_new_session=os.name != WINDOWS_OS_NAME,
    )


def _drain_process_after_tree_kill(
    review_process: subprocess.Popen[str],
) -> None:
    """Join pipe reader threads after a tree kill; never block unbounded.

    ::

        kill tree -> communicate(grace)    ok: pipe EOF, threads join
        kill incomplete, no drain          flag: Popen.__exit__ wait() hangs

    Windows needs a post-kill ``communicate()`` so timed-out reader threads
    join. Every platform needs a timed join so an incomplete tree kill cannot
    leave ``Popen.__exit__`` waiting forever.
    """
    try:
        review_process.communicate(timeout=PROCESS_TREE_KILL_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            review_process.kill()
        except ProcessLookupError:
            return
        try:
            review_process.communicate(timeout=PROCESS_TREE_KILL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return


def _communicate_with_tree_kill_on_timeout(
    review_process: subprocess.Popen[str],
    timeout_seconds: float | None,
) -> tuple[str, str]:
    """Drain the process; on timeout kill its whole tree, drain again, re-raise.

    ::

        codex -> codex.exe -> code-mode-host   grandchildren hold the stdout pipe
        kill only the parent on timeout        drain waits for EOF, hangs
        ok: kill the whole tree, then drain    pipe reaches EOF, timeout raised

    Killing only the direct child on a timeout leaves grandchildren holding the
    capture pipe open, so the drain read never reaches end-of-file and blocks
    forever. Killing the entire tree and then draining with a grace timeout lets
    the pipe reach end-of-file without an unbounded wait.
    """
    try:
        return review_process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(review_process)
        _drain_process_after_tree_kill(review_process)
        raise


def _completed_from_streams(
    all_arguments: list[str],
    review_return_code: int,
    captured_stdout: str,
    captured_stderr: str,
    should_check: bool,
) -> subprocess.CompletedProcess[str]:
    """Wrap captured streams in a CompletedProcess, honoring the check flag."""
    completed_process = subprocess.CompletedProcess(
        all_arguments, review_return_code, captured_stdout, captured_stderr
    )
    if should_check:
        completed_process.check_returncode()
    return completed_process


def _optional_timeout_seconds(requested_timeout: object) -> float | None:
    """Return a numeric timeout as float, or None when it is not a number."""
    if isinstance(requested_timeout, (int, float)):
        return float(requested_timeout)
    return None


def _run_codex_process(
    all_arguments: list[str],
    **all_keyword_arguments: object,
) -> subprocess.CompletedProcess[str]:
    """Run a codex process, killing its whole child tree on a timeout.

    Mirrors the ``subprocess.run`` keyword arguments the review wrapper passes:
    ``cwd``, ``capture_output``, ``text``, ``encoding``, ``check``, ``timeout``,
    and ``env``.
    """
    timeout_seconds = _optional_timeout_seconds(all_keyword_arguments.get(TIMEOUT_KEYWORD))
    should_check = bool(all_keyword_arguments.get(CHECK_KEYWORD, False))
    with _open_codex_popen(all_arguments, all_keyword_arguments) as review_process:
        captured_stdout, captured_stderr = _communicate_with_tree_kill_on_timeout(
            review_process, timeout_seconds
        )
        review_return_code = review_process.returncode
    return _completed_from_streams(
        all_arguments,
        review_return_code,
        captured_stdout,
        captured_stderr,
        should_check,
    )


codex_subprocess_runner = _run_codex_process


@dataclass(frozen=True)
class CodexReviewOutcome:
    """Captured result of one probe-plus-review attempt.

    ::

        CodexReviewOutcome(
            outcome_class="completed",
            exit_code=0,
            binary_version="0.144.3",
            jsonl_path=Path("run_state/codex-review.jsonl"),
            agent_message="No issues found.",
        )

    Attributes:
        outcome_class: Capture-boundary class ``completed`` or ``codex_down``.
            Callers treat this field as the success signal; ``exit_code`` alone
            is not enough (a shape probe can exit 0 while flags are missing).
        exit_code: Last process exit code, or a sentinel when none ran.
        binary_version: Parsed ``codex --version`` string, or empty.
        jsonl_path: Captured JSONL path, or None when review did not run.
        agent_message: Last JSONL ``agent_message`` text when present; on a
            non-zero review exit, falls back to stderr text when JSONL has no
            agent message (config and argument errors land on stderr).
    """

    outcome_class: str
    exit_code: int
    binary_version: str
    jsonl_path: Path | None
    agent_message: str


def _down(*, exit_code: int, binary_version: str) -> CodexReviewOutcome:
    return CodexReviewOutcome(
        outcome_class=OUTCOME_CLASS_CODEX_DOWN,
        exit_code=exit_code,
        binary_version=binary_version,
        jsonl_path=None,
        agent_message="",
    )


def _resolve_codex_command_prefix() -> list[str]:
    """Resolve the codex launch prefix, wrapping a Windows ``.cmd``/``.bat`` shim.

    ::

        POSIX codex on PATH   ->  ["/usr/local/bin/codex"]
        Windows codex.cmd     ->  ["cmd", "/c", "C:\\...\\codex.cmd"]
        codex not on PATH     ->  ["codex"]      (downstream FileNotFoundError)

    ``CreateProcess`` resolves a bare name only against ``.exe``, so a bare
    ``codex`` never finds the npm shim; the ``cmd /c`` wrap runs it.
    """
    codex_path = shutil.which(CODEX_BINARY_NAME)
    if codex_path is None:
        return [CODEX_BINARY_NAME]
    if os.name == WINDOWS_OS_NAME and codex_path.lower().endswith(
        ALL_WINDOWS_SCRIPT_SUFFIXES
    ):
        return [WINDOWS_COMMAND_SHELL, WINDOWS_COMMAND_SHELL_RUN_FLAG, codex_path]
    return [codex_path]


def _run_command(
    all_arguments: list[str],
    *,
    working_directory: Path | None,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return codex_subprocess_runner(
        all_arguments,
        cwd=str(working_directory) if working_directory is not None else None,
        capture_output=True,
        text=True,
        encoding=UTF8_ENCODING,
        check=False,
        timeout=timeout_seconds,
        env=dict(os.environ),
    )


def _safe_run(
    all_arguments: list[str],
    *,
    working_directory: Path | None,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str] | int:
    try:
        return _run_command(
            all_arguments,
            working_directory=working_directory,
            timeout_seconds=timeout_seconds,
        )
    except FileNotFoundError:
        if working_directory is not None and not working_directory.is_dir():
            raise
        return MISSING_BINARY_EXIT_CODE
    except subprocess.TimeoutExpired:
        return TIMEOUT_EXIT_CODE
    except UnicodeDecodeError:
        return SUBPROCESS_DECODE_EXIT_CODE


def _parse_binary_version(version_stdout: str) -> str:
    version_match = re.search(VERSION_PROBE_PATTERN, version_stdout)
    if version_match is None:
        return version_stdout.strip()
    return version_match.group(1)


def _probe_binary_version(timeout_seconds: int) -> tuple[str, int | None]:
    completion_or_exit = _safe_run(
        [*_resolve_codex_command_prefix(), VERSION_FLAG],
        working_directory=None,
        timeout_seconds=timeout_seconds,
    )
    if isinstance(completion_or_exit, int):
        return "", completion_or_exit
    if completion_or_exit.returncode != 0:
        return "", completion_or_exit.returncode
    return _parse_binary_version(completion_or_exit.stdout), None


def _probe_review_shape(timeout_seconds: int) -> tuple[bool, int]:
    completion_or_exit = _safe_run(
        [*_resolve_codex_command_prefix(), EXEC_SUBCOMMAND, REVIEW_SUBCOMMAND, HELP_FLAG],
        working_directory=None,
        timeout_seconds=timeout_seconds,
    )
    if isinstance(completion_or_exit, int):
        return False, completion_or_exit
    if completion_or_exit.returncode != 0:
        return False, completion_or_exit.returncode
    help_text = f"{completion_or_exit.stdout}{completion_or_exit.stderr}"
    has_required_flags = all(
        _help_text_contains_flag(help_text, each_flag)
        for each_flag in ALL_SHAPE_PROBE_REQUIRED_FLAGS
    )
    return has_required_flags, completion_or_exit.returncode


def _help_text_contains_flag(help_text: str, flag_name: str) -> bool:
    flag_token_pattern = re.compile(
        re.escape(flag_name) + SHAPE_FLAG_TOKEN_TAIL_PATTERN
    )
    return flag_token_pattern.search(help_text) is not None


def _require_single_target(
    *,
    base_branch: str | None,
    is_uncommitted: bool,
    commit_sha: str | None,
    is_prompt_target: bool,
) -> None:
    selected_target_count = sum(
        [
            base_branch is not None,
            is_uncommitted,
            commit_sha is not None,
            is_prompt_target,
        ]
    )
    if selected_target_count != 1:
        raise ValueError(
            "exactly one of base_branch, is_uncommitted, commit_sha, "
            "or is_prompt_target must be selected"
        )


def _require_existing_directory(directory_path: Path, parameter_name: str) -> None:
    if not directory_path.is_dir():
        raise ValueError(
            f"{parameter_name} is not an existing directory: {directory_path}"
        )


def _build_review_arguments(
    *,
    base_branch: str | None,
    is_uncommitted: bool,
    commit_sha: str | None,
    is_prompt_target: bool,
) -> list[str]:
    all_arguments = [*_resolve_codex_command_prefix(), EXEC_SUBCOMMAND]
    if CODEX_MODEL_PIN:
        all_arguments.extend([MODEL_FLAG, CODEX_MODEL_PIN])
    all_arguments.extend([REVIEW_SUBCOMMAND, JSON_FLAG])
    if is_uncommitted:
        all_arguments.append(UNCOMMITTED_TARGET_FLAG)
    elif base_branch is not None:
        all_arguments.extend([BASE_TARGET_FLAG, base_branch])
    elif commit_sha is not None:
        all_arguments.extend([COMMIT_TARGET_FLAG, commit_sha])
    elif is_prompt_target:
        all_arguments.append(CUSTOM_INSTRUCTIONS_PROMPT)
    return all_arguments


def _extract_agent_message(jsonl_text: str) -> str:
    agent_message_text = ""
    for each_line in jsonl_text.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        try:
            event_payload = json.loads(stripped_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event_payload, dict):
            continue
        if event_payload.get(JSONL_EVENT_TYPE_KEY) != JSONL_ENTRY_COMPLETED_TYPE:
            continue
        entry_payload = event_payload.get(JSONL_ENTRY_KEY)
        if not isinstance(entry_payload, dict):
            continue
        if entry_payload.get(JSONL_EVENT_TYPE_KEY) != JSONL_AGENT_MESSAGE_TYPE:
            continue
        message_text = entry_payload.get(JSONL_AGENT_MESSAGE_TEXT_KEY)
        if isinstance(message_text, str):
            agent_message_text = message_text
    return agent_message_text


def _probe_or_down(timeout_seconds: int) -> CodexReviewOutcome | str:
    binary_version, version_failure_exit_code = _probe_binary_version(timeout_seconds)
    if version_failure_exit_code is not None:
        return _down(
            exit_code=version_failure_exit_code,
            binary_version=binary_version,
        )
    is_shape_supported, shape_exit_code = _probe_review_shape(timeout_seconds)
    if not is_shape_supported:
        return _down(exit_code=shape_exit_code, binary_version=binary_version)
    return binary_version


def _capture_review_run(
    *,
    repository_directory: Path,
    run_state_directory: Path,
    all_review_arguments: list[str],
    timeout_seconds: int,
    binary_version: str,
) -> CodexReviewOutcome:
    completion_or_exit = _safe_run(
        all_review_arguments,
        working_directory=repository_directory,
        timeout_seconds=timeout_seconds,
    )
    if isinstance(completion_or_exit, int):
        return _down(exit_code=completion_or_exit, binary_version=binary_version)
    jsonl_text = completion_or_exit.stdout or ""
    stderr_text = completion_or_exit.stderr or ""
    jsonl_path = run_state_directory / JSONL_CAPTURE_FILENAME
    run_state_directory.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        jsonl_text,
        encoding=UTF8_ENCODING,
        newline=JSONL_CAPTURE_NEWLINE,
    )
    review_returncode = completion_or_exit.returncode
    if review_returncode != 0:
        return CodexReviewOutcome(
            outcome_class=OUTCOME_CLASS_CODEX_DOWN,
            exit_code=review_returncode,
            binary_version=binary_version,
            jsonl_path=jsonl_path,
            agent_message=_extract_agent_message(jsonl_text) or stderr_text,
        )
    return CodexReviewOutcome(
        outcome_class=OUTCOME_CLASS_COMPLETED,
        exit_code=review_returncode,
        binary_version=binary_version,
        jsonl_path=jsonl_path,
        agent_message=_extract_agent_message(jsonl_text),
    )


def run_codex_review(
    *,
    repository_directory: Path,
    run_state_directory: Path,
    base_branch: str | None = None,
    is_uncommitted: bool = False,
    commit_sha: str | None = None,
    is_prompt_target: bool = False,
    timeout_seconds: int | None = None,
) -> CodexReviewOutcome:
    """Run one Codex review against a single target and capture its outputs.

    Capture-only boundary: returns ``completed`` or ``codex_down`` plus raw
    capture fields. Skill-level classes ``down`` / ``clean`` / ``findings``
    come from a later classifier that reads this outcome.

    ::

        ok:   outcome_class == "completed" and exit_code == 0
        flag: outcome_class == "codex_down" even when exit_code == 0
              (shape probe ran, required flags missing)

    Args:
        repository_directory: Repository root used as the process cwd.
        run_state_directory: Existing directory that receives the JSONL stream
            file. The caller creates this directory before the call.
        base_branch: Base branch for ``--base``; exclusive with other targets.
        is_uncommitted: When True, uses ``--uncommitted``.
        commit_sha: Commit SHA for ``--commit``; exclusive with other targets.
        is_prompt_target: When True, uses the custom-instructions PROMPT target.
        timeout_seconds: Per-invocation timeout; defaults from constants.

    Returns:
        Capture outcome (``completed`` / ``codex_down``), process exit code,
        binary version, JSONL path, and agent text (JSONL agent_message, or
        stderr on a failed review when JSONL has no agent message).

    Raises:
        ValueError: When zero targets or more than one target is selected, or
            when ``repository_directory`` or ``run_state_directory`` is not an
            existing directory. Both directories are checked before any Codex
            process starts, so a bad path costs no review run.
    """
    _require_single_target(
        base_branch=base_branch,
        is_uncommitted=is_uncommitted,
        commit_sha=commit_sha,
        is_prompt_target=is_prompt_target,
    )
    _require_existing_directory(repository_directory, "repository_directory")
    _require_existing_directory(run_state_directory, "run_state_directory")
    resolved_timeout_seconds = (
        DEFAULT_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    )
    probe_outcome = _probe_or_down(resolved_timeout_seconds)
    if isinstance(probe_outcome, CodexReviewOutcome):
        return probe_outcome
    return _capture_review_run(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        all_review_arguments=_build_review_arguments(
            base_branch=base_branch,
            is_uncommitted=is_uncommitted,
            commit_sha=commit_sha,
            is_prompt_target=is_prompt_target,
        ),
        timeout_seconds=resolved_timeout_seconds,
        binary_version=probe_outcome,
    )
