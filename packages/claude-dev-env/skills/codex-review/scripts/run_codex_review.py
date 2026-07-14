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
import subprocess
from dataclasses import dataclass
from pathlib import Path

from codex_review_scripts_constants.run_constants import (
    ALL_SHAPE_PROBE_REQUIRED_FLAGS,
    BASE_TARGET_FLAG,
    CODEX_BINARY_NAME,
    CODEX_MODEL_PIN,
    COMMIT_TARGET_FLAG,
    CUSTOM_INSTRUCTIONS_PROMPT,
    DEFAULT_TIMEOUT_SECONDS,
    EXEC_SUBCOMMAND,
    HELP_FLAG,
    JSON_FLAG,
    JSONL_AGENT_MESSAGE_TEXT_KEY,
    JSONL_AGENT_MESSAGE_TYPE,
    JSONL_CAPTURE_FILENAME,
    JSONL_ENTRY_COMPLETED_TYPE,
    JSONL_ENTRY_KEY,
    JSONL_EVENT_TYPE_KEY,
    MISSING_BINARY_EXIT_CODE,
    MODEL_FLAG,
    OUTCOME_CLASS_CODEX_DOWN,
    OUTCOME_CLASS_COMPLETED,
    REVIEW_SUBCOMMAND,
    SHAPE_FLAG_TOKEN_TAIL_PATTERN,
    SUBPROCESS_DECODE_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    UNCOMMITTED_TARGET_FLAG,
    UTF8_ENCODING,
    VERSION_FLAG,
    VERSION_PROBE_PATTERN,
)

codex_subprocess_runner = subprocess.run


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
        [CODEX_BINARY_NAME, VERSION_FLAG],
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
        [CODEX_BINARY_NAME, EXEC_SUBCOMMAND, REVIEW_SUBCOMMAND, HELP_FLAG],
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


def _build_review_arguments(
    *,
    base_branch: str | None,
    is_uncommitted: bool,
    commit_sha: str | None,
    is_prompt_target: bool,
) -> list[str]:
    all_arguments = [CODEX_BINARY_NAME, EXEC_SUBCOMMAND]
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
    jsonl_path.write_text(jsonl_text, encoding=UTF8_ENCODING)
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
        ValueError: When zero targets or more than one target is selected.
    """
    _require_single_target(
        base_branch=base_branch,
        is_uncommitted=is_uncommitted,
        commit_sha=commit_sha,
        is_prompt_target=is_prompt_target,
    )
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
