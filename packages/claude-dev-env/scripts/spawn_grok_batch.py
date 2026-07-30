#!/usr/bin/env python3
"""Batch launcher and report collector for fleets of headless grok workers.

Loads a JSON batch specification, gates once through ``run_preflight``,
assembles each worker prompt from part files, mints unique prompt, report,
leader-socket, and debug paths under the run state directory, staggers starts,
and launches each worker through ``run_headless_worker``. Emits one batch
summary JSON on stdout.

Import ``run_grok_batch`` for the summary object, or run the module as a CLI::

    python spawn_grok_batch.py --spec batch.json --run-temp-dir <dir>
"""

from __future__ import annotations

import argparse
import subprocess
import json
import sys
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from dev_env_scripts_constants.grok_worker_constants import (
    ALL_KNOWN_TOOL_PROFILES,
    ALL_KNOWN_WORKER_SPEC_KEYS,
    BATCH_LAUNCH_ERROR_STDERR_PREFIX,
    BATCH_SPEC_ROLE_KEY,
    BATCH_SPEC_SHOULD_PING_KEY,
    BATCH_SPEC_WORKERS_KEY,
    BUILD_PROFILE_PROMPT_HEADER,
    CLASSIFICATION_ERROR,
    CLI_BATCH_SPEC_FLAG,
    CLI_RUN_STATE_DIR_FLAG,
    DEBUG_FILE_FLAG,
    DEBUG_FILENAME_PREFIX,
    DEBUG_FILENAME_SUFFIX,
    DEFAULT_ROLE,
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    DISABLE_WEB_SEARCH_FLAG,
    DISALLOWED_TOOLS_FLAG,
    LEADER_SOCKET_FILENAME_PREFIX,
    LEADER_SOCKET_FILENAME_SUFFIX,
    MAXIMUM_WORKER_TIMEOUT_ERROR_TEMPLATE,
    MAXIMUM_WORKER_TIMEOUT_SECONDS,
    MIN_WORKER_TIMEOUT_SECONDS,
    MINIMUM_WORKER_TIMEOUT_ERROR_TEMPLATE,
    OUTPUT_FILENAME_PREFIX,
    OUTPUT_FILENAME_SUFFIX,
    PROMPT_FILENAME_PREFIX,
    PROMPT_FILENAME_SUFFIX,
    PROMPT_PART_JOIN_SEPARATOR,
    READONLY_DISALLOWED_TOOLS_VALUE,
    READONLY_PROFILE_PROMPT_HEADER,
    REPORT_STREAM_JOIN_SEPARATOR,
    SUMMARY_CLASSIFICATION_KEY,
    SUMMARY_DEBUG_FILE_KEY,
    SUMMARY_IS_OK_KEY,
    SUMMARY_IS_PREFLIGHT_USABLE_KEY,
    SUMMARY_LEADER_SOCKET_KEY,
    SUMMARY_OUTPUT_FILE_KEY,
    SUMMARY_PREFLIGHT_REASON_KEY,
    SUMMARY_PROMPT_FILE_KEY,
    SUMMARY_REPORT_TEXT_KEY,
    SUMMARY_RETURNCODE_KEY,
    SUMMARY_ROLE_NAME_KEY,
    SUMMARY_TOOL_PROFILE_KEY,
    SUMMARY_WORKERS_KEY,
    TOOL_PROFILE_BUILD,
    TOOL_PROFILE_READONLY,
    UNKNOWN_WORKER_KEY_ERROR_TEMPLATE,
    UTF8_ENCODING,
    WORKER_EXCEPTION_RETURN_CODE,
    WORKER_SPEC_AGENT_NAME_KEY,
    WORKER_SPEC_CWD_KEY,
    WORKER_SPEC_IS_REPO_ONLY_KEY,
    WORKER_SPEC_KEY_JOIN_SEPARATOR,
    WORKER_SPEC_PROMPT_PARTS_KEY,
    WORKER_SPEC_ROLE_NAME_KEY,
    WORKER_SPEC_TIMEOUT_KEY,
    WORKER_SPEC_TOOL_PROFILE_KEY,
    BATCH_SPEC_ADVISOR_KEY,
    ADVISOR_SPEC_LAUNCHER_KEY,
    ADVISOR_SPEC_MODEL_KEY,
    ADVISOR_SPEC_EFFORT_KEY,
    DEFAULT_ADVISOR_LAUNCHER_PLACEHOLDER,
    DEFAULT_ADVISOR_MODEL,
    DEFAULT_ADVISOR_EFFORT,
    MAXIMUM_WORKER_ADVISOR_CORRECTIONS,
    MAXIMUM_ADVISOR_TIMEOUT_SECONDS,
    ADVISOR_SIGNAL_ENDORSE,
    ADVISOR_SIGNAL_CORRECTION,
    ADVISOR_SIGNAL_PLAN,
    ADVISOR_SIGNAL_STOP,
    ALL_KNOWN_ADVISOR_SIGNALS,
    CLASSIFICATION_ADVISOR_BLOCKED,
    PENDING_BIND_SENTINEL,
    ADVISOR_PROMPT_HEADER_TEMPLATE,
    SUMMARY_ADVISOR_SESSION_ID_KEY,
    SUMMARY_ADVISOR_SIGNAL_KEY,
    SUMMARY_ADVISOR_LAUNCHER_KEY,
    ADVISOR_CLI_PRINT_FLAG,
    ADVISOR_CLI_MODEL_FLAG,
    ADVISOR_CLI_EFFORT_FLAG,
    ADVISOR_CLI_OUTPUT_FORMAT_FLAG,
    ADVISOR_CLI_OUTPUT_FORMAT_JSON,
    ADVISOR_CLI_RESUME_FLAG,
    ADVISOR_BIND_PROMPT_TEMPLATE,
    ADVISOR_VERDICT_PROMPT_TEMPLATE,
)
from dev_env_scripts_constants.timing import WORKER_STAGGER_SECONDS
from grok_headless_runner import GrokRunnerOutcome, run_headless_worker
from grok_worker_preflight import PreflightOutcome, run_preflight

class AdvisorFailureError(ValueError):
    """Raised when an advisor bind, resume, or launcher call fails closed."""


batch_sleep = time.sleep
batch_headless_runner = run_headless_worker
batch_preflight = run_preflight


def extract_advisor_signal(advisor_text: str) -> str | None:
    """Return the first allowed opening signal token from advisor text.

    ::

        extract_advisor_signal("ENDORSE\\nlooks good")
        ok: "ENDORSE"
        extract_advisor_signal("hello ENDORSE")
        flag: None

    Args:
        advisor_text: Raw advisor reply body.

    Returns:
        One of the four known signals, or ``None`` when the first token is
        missing or outside the set.
    """
    stripped = (advisor_text or "").strip()
    if not stripped:
        return None
    first_line = stripped.splitlines()[0].strip()
    first_token = first_line.split()[0] if first_line else ""
    if first_token in ALL_KNOWN_ADVISOR_SIGNALS:
        return first_token
    return None


def _parse_advisor_spec(raw_advisor: object) -> AdvisorSpec | None:
    if raw_advisor is None:
        return None
    if not isinstance(raw_advisor, dict):
        raise ValueError("batch advisor must be an object when present")
    launcher = raw_advisor.get(
        ADVISOR_SPEC_LAUNCHER_KEY, DEFAULT_ADVISOR_LAUNCHER_PLACEHOLDER
    )
    model = raw_advisor.get(ADVISOR_SPEC_MODEL_KEY, DEFAULT_ADVISOR_MODEL)
    effort = raw_advisor.get(ADVISOR_SPEC_EFFORT_KEY, DEFAULT_ADVISOR_EFFORT)
    if not isinstance(launcher, str) or not launcher:
        raise ValueError("advisor.launcher must be a non-empty string")
    if launcher == PENDING_BIND_SENTINEL:
        raise ValueError(f"advisor.launcher must not be {PENDING_BIND_SENTINEL}")
    if not isinstance(model, str) or not model:
        raise ValueError("advisor.model must be a non-empty string")
    if not isinstance(effort, str) or not effort:
        raise ValueError("advisor.effort must be a non-empty string")
    return AdvisorSpec(launcher=launcher, model=model, effort=effort)


def _advisor_body_text_from_stdout(stdout_text: str) -> str:
    stripped = (stdout_text or "").strip()
    if not stripped:
        return ""
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    if isinstance(parsed, dict):
        advisor_body_field = parsed.get("result")
        if isinstance(advisor_body_field, str):
            return advisor_body_field
        return stripped
    if isinstance(parsed, list):
        for each_record in reversed(parsed):
            if (
                isinstance(each_record, dict)
                and each_record.get("type") == "result"
                and isinstance(each_record.get("result"), str)
            ):
                return each_record["result"]
        return stripped
    return stripped


def _session_id_from_advisor_stdout(stdout_text: str) -> str | None:
    stripped = (stdout_text or "").strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    candidates: list[object] = []
    if isinstance(parsed, dict):
        candidates.append(parsed)
    elif isinstance(parsed, list):
        candidates.extend(each for each in parsed if isinstance(each, dict))
    for each_record in candidates:
        session_id = each_record.get("session_id")
        if isinstance(session_id, str) and session_id and session_id != PENDING_BIND_SENTINEL:
            return session_id
    return None


def invoke_advisor_launcher(
    *,
    launcher: str,
    model: str,
    effort: str,
    prompt_text: str,
    session_id: str | None = None,
) -> tuple[str | None, str, int]:
    """Run one advisor launcher call via direct subprocess.

    Args:
        launcher: Spec-supplied executable name (runtime only).
        model: Advisor model name.
        effort: Advisor effort level.
        prompt_text: Prompt body piped on stdin.
        session_id: When set, pass ``--resume`` for a post-report consult.

    Returns:
        ``(session_id_or_none, advisor_body_text, returncode)``.
    """
    all_command_arguments = [
        launcher,
        ADVISOR_CLI_PRINT_FLAG,
        ADVISOR_CLI_MODEL_FLAG,
        model,
        ADVISOR_CLI_EFFORT_FLAG,
        effort,
        ADVISOR_CLI_OUTPUT_FORMAT_FLAG,
        ADVISOR_CLI_OUTPUT_FORMAT_JSON,
    ]
    if session_id is not None:
        all_command_arguments.extend([ADVISOR_CLI_RESUME_FLAG, session_id])
    try:
        completion = subprocess.run(
            all_command_arguments,
            input=prompt_text,
            capture_output=True,
            text=True,
            encoding=UTF8_ENCODING,
            check=False,
            timeout=MAXIMUM_ADVISOR_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as missing_launcher:
        raise AdvisorFailureError(
            f"advisor launcher not found: {launcher}"
        ) from missing_launcher
    except subprocess.TimeoutExpired as timed_out:
        raise AdvisorFailureError(
            f"advisor launcher timed out after {MAXIMUM_ADVISOR_TIMEOUT_SECONDS}s"
        ) from timed_out
    stdout_text = completion.stdout or ""
    resolved_session = _session_id_from_advisor_stdout(stdout_text)
    if session_id is not None and resolved_session is None:
        resolved_session = session_id
    advisor_body_text = _advisor_body_text_from_stdout(stdout_text)
    return resolved_session, advisor_body_text, completion.returncode


batch_invoke_advisor = invoke_advisor_launcher


def bind_unique_worker_advisor(
    *,
    advisor_spec: AdvisorSpec,
    role_name: str,
    all_used_session_ids: set[str],
) -> tuple[str, str]:
    """Bind one unique advisor session for a worker; refuse duplicates and sentinels.

    ::

        bind_unique_worker_advisor(...)
        ok: returns (session_id, ENDORSE)
        flag: duplicate session id across workers raises ValueError

    Args:
        advisor_spec: Lead-supplied launcher/model/effort.
        role_name: Worker role used in the bind prompt.
        all_used_session_ids: Sessions already issued in this batch.

    Returns:
        ``(session_id, opening_signal)``.

    Raises:
        ValueError: On bind failure, sentinel, missing signal, or duplicate id.
    """
    if advisor_spec.launcher == DEFAULT_ADVISOR_LAUNCHER_PLACEHOLDER:
        raise ValueError(
            "advisor.launcher still holds the placeholder; supply a real launcher in the batch spec"
        )
    if advisor_spec.launcher == PENDING_BIND_SENTINEL:
        raise ValueError(f"advisor.launcher is {PENDING_BIND_SENTINEL}")
    prompt_text = ADVISOR_BIND_PROMPT_TEMPLATE.format(role_name=role_name)
    session_id, advisor_body_text, returncode = batch_invoke_advisor(
        launcher=advisor_spec.launcher,
        model=advisor_spec.model,
        effort=advisor_spec.effort,
        prompt_text=prompt_text,
    )
    if returncode != 0 or not session_id or session_id == PENDING_BIND_SENTINEL:
        raise AdvisorFailureError(
            f"advisor bind failed for role {role_name}: returncode={returncode}"
        )
    if session_id in all_used_session_ids:
        raise AdvisorFailureError(
            f"duplicate advisor session id {session_id} for role {role_name}"
        )
    signal = extract_advisor_signal(advisor_body_text)
    if signal is None:
        raise ValueError(f"malformed advisor signal for role {role_name}")
    if signal == ADVISOR_SIGNAL_STOP:
        raise ValueError(f"advisor STOP for role {role_name}")
    if signal != ADVISOR_SIGNAL_ENDORSE:
        raise ValueError(
            f"advisor pre-dispatch signal {signal} for role {role_name}; require ENDORSE"
        )
    all_used_session_ids.add(session_id)
    return session_id, signal


def obtain_advisor_completion_verdict(
    *,
    advisor_spec: AdvisorSpec,
    role_name: str,
    session_id: str,
    report_text: str,
) -> str:
    """Resume the same advisor session until ENDORSE or the correction cap.

    Args:
        advisor_spec: Lead-supplied launcher/model/effort.
        role_name: Worker role name.
        session_id: Session from pre-dispatch bind.
        report_text: Worker report body under review.

    Returns:
        The final accepted signal (``ENDORSE``).

    Raises:
        ValueError: On STOP, malformed signal, or correction cap exceeded.
    """
    if session_id == PENDING_BIND_SENTINEL:
        raise ValueError(f"advisor session_id is {PENDING_BIND_SENTINEL}")
    correction_count = 0
    while True:
        prompt_text = ADVISOR_VERDICT_PROMPT_TEMPLATE.format(
            role_name=role_name,
            session_id=session_id,
            report_text=report_text,
        )
        _, advisor_body_text, returncode = batch_invoke_advisor(
            launcher=advisor_spec.launcher,
            model=advisor_spec.model,
            effort=advisor_spec.effort,
            prompt_text=prompt_text,
            session_id=session_id,
        )
        if returncode != 0:
            raise ValueError(
                f"advisor resume failed for role {role_name}: returncode={returncode}"
            )
        signal = extract_advisor_signal(advisor_body_text)
        if signal is None:
            raise ValueError(f"malformed advisor signal for role {role_name}")
        if signal == ADVISOR_SIGNAL_ENDORSE:
            return signal
        if signal == ADVISOR_SIGNAL_STOP:
            raise ValueError(f"advisor STOP for role {role_name}")
        if signal in (ADVISOR_SIGNAL_CORRECTION, ADVISOR_SIGNAL_PLAN):
            correction_count += 1
            if correction_count > MAXIMUM_WORKER_ADVISOR_CORRECTIONS:
                raise ValueError(
                    f"advisor correction cap exceeded for role {role_name}"
                )
            continue
        raise ValueError(f"unexpected advisor signal {signal} for role {role_name}")



def _require_known_worker_keys(all_worker_fields: dict[str, object]) -> None:
    """Reject a worker entry carrying a key the launcher does not accept.

    ::

        {"role_name": "lens", ..., "timeout_second": <seconds>}
        flag: unknown worker key(s): timeout_second; accepted keys: agent_name, ...

    A dropped key reads as a setting that took effect. Naming it here makes
    that a startup error rather than a silent gap.

    Args:
        all_worker_fields: One raw worker entry straight from the JSON spec.

    Raises:
        ValueError: When the entry carries any key outside the accepted set.
    """
    all_unknown_keys = set(all_worker_fields) - ALL_KNOWN_WORKER_SPEC_KEYS
    if not all_unknown_keys:
        return
    joined_unknown = WORKER_SPEC_KEY_JOIN_SEPARATOR.join(sorted(all_unknown_keys))
    joined_accepted = WORKER_SPEC_KEY_JOIN_SEPARATOR.join(
        sorted(ALL_KNOWN_WORKER_SPEC_KEYS)
    )
    raise ValueError(
        UNKNOWN_WORKER_KEY_ERROR_TEMPLATE.format(
            unknown_keys=joined_unknown,
            accepted_keys=joined_accepted,
        )
    )


@dataclass(frozen=True)
class WorkerSpec:
    """One worker entry from a batch specification."""

    role_name: str
    all_prompt_part_paths: tuple[Path, ...]
    working_directory: Path
    tool_profile: str
    timeout_seconds: int
    is_repo_only: bool = False
    agent_name: str | None = None


@dataclass(frozen=True)
class AdvisorSpec:
    """Lead-supplied worker advisor binding configuration for one batch.

    The launcher name is runtime-only: the committed default is the placeholder
    ``DEFAULT_ADVISOR_LAUNCHER_PLACEHOLDER``. The lead replaces it in the batch
    specification; real account-scoped launcher names never land as constants.
    """

    launcher: str
    model: str = DEFAULT_ADVISOR_MODEL
    effort: str = DEFAULT_ADVISOR_EFFORT


@dataclass(frozen=True)
class BatchSpec:
    """Full batch specification for one fleet launch."""

    role: str
    should_ping: bool
    all_workers: tuple[WorkerSpec, ...]
    advisor: AdvisorSpec | None = None


@dataclass(frozen=True)
class WorkerScratchPaths:
    """Per-worker paths minted under the run state directory."""

    prompt_path: Path
    report_path: Path
    leader_socket_path: Path
    debug_path: Path


@dataclass(frozen=True)
class WorkerReport:
    """Collected outcome for one launched worker."""

    role_name: str
    tool_profile: str
    returncode: int
    classification: str
    is_ok: bool
    report_text: str
    report_path: str
    leader_socket: str
    prompt_path: str
    debug_path: str
    advisor_session_id: str | None = None
    advisor_completion_signal: str | None = None
    advisor_launcher: str | None = None


@dataclass(frozen=True)
class BatchSummary:
    """Preflight gate result plus per-worker reports for one batch run."""

    is_preflight_usable: bool
    preflight_reason: str | None
    all_worker_reports: tuple[WorkerReport, ...]


def _profile_prompt_header(tool_profile: str) -> str:
    if tool_profile == TOOL_PROFILE_BUILD:
        return BUILD_PROFILE_PROMPT_HEADER
    return READONLY_PROFILE_PROMPT_HEADER


def assemble_worker_prompt(
    *,
    all_prompt_part_paths: tuple[Path, ...],
    tool_profile: str,
) -> str:
    """Assemble one worker prompt from a tool-profile header and part files.

    ::

        assemble_worker_prompt(
            all_prompt_part_paths=(header, body), tool_profile="build"
        )
        ok: starts with BUILD_PROFILE_PROMPT_HEADER and joins part bodies

    Args:
        all_prompt_part_paths: Ordered paths whose text bodies form the prompt.
        tool_profile: ``readonly`` or ``build``; selects the leading header.

    Returns:
        The full prompt text written to the per-worker prompt file.
    """
    all_part_bodies = [
        each_path.read_text(encoding=UTF8_ENCODING)
        for each_path in all_prompt_part_paths
    ]
    joined_parts = PROMPT_PART_JOIN_SEPARATOR.join(all_part_bodies)
    return f"{_profile_prompt_header(tool_profile)}{joined_parts}"


def build_tool_profile_arguments(
    *,
    tool_profile: str,
    is_repo_only: bool,
    debug_file: Path,
) -> tuple[str, ...]:
    """Build the extra CLI tokens for one worker's tool profile.

    ::

        build_tool_profile_arguments(tool_profile="readonly", is_repo_only=True, ...)
        ok: includes --disallowed-tools and --disable-web-search
        flag: build profile omits both tool-restriction flags

    Args:
        tool_profile: ``readonly`` or ``build``.
        is_repo_only: When True with readonly, also disable web search.
        debug_file: Per-worker debug log path passed via ``--debug-file``.

    Returns:
        Extra argv tokens appended after the runner's base invocation.
    """
    all_extra_arguments: list[str] = [DEBUG_FILE_FLAG, str(debug_file)]
    if tool_profile != TOOL_PROFILE_READONLY:
        return tuple(all_extra_arguments)
    all_extra_arguments.extend(
        [DISALLOWED_TOOLS_FLAG, READONLY_DISALLOWED_TOOLS_VALUE]
    )
    if is_repo_only:
        all_extra_arguments.append(DISABLE_WEB_SEARCH_FLAG)
    return tuple(all_extra_arguments)


def _mint_worker_path(
    run_state_directory: Path, *, prefix: str, suffix: str
) -> Path:
    unique_token = uuid.uuid4().hex
    return run_state_directory / f"{prefix}{unique_token}{suffix}"


def _require_string(raw_field: object, field_name: str) -> str:
    if not isinstance(raw_field, str):
        raise ValueError(f"worker {field_name} must be a string")
    return raw_field


def _require_int(raw_field: object, field_name: str) -> int:
    if isinstance(raw_field, bool) or not isinstance(raw_field, int):
        raise ValueError(f"worker {field_name} must be an int")
    return raw_field


def _require_bool(raw_field: object, field_name: str) -> bool:
    if not isinstance(raw_field, bool):
        raise ValueError(f"worker {field_name} must be a bool")
    return raw_field


def _require_worker_field(
    all_worker_fields: dict[str, object], field_name: str
) -> object:
    if field_name not in all_worker_fields:
        raise ValueError(f"worker missing required field: {field_name}")
    return all_worker_fields[field_name]


def _require_timeout_within_bounds(raw_field: object) -> int:
    """Accept a worker timeout inside the bounds; refuse anything outside them.

    ::

        0     flag: ValueError naming MIN_WORKER_TIMEOUT_SECONDS
        5401  flag: ValueError naming MAXIMUM_WORKER_TIMEOUT_SECONDS
        5400  ok:   returned untouched
        30    ok:   returned untouched

    Rejecting here rather than clamping keeps the fault where the operator
    wrote it. The runner repeats the check for callers that skip the parse.

    Args:
        raw_field: The parsed ``timeout_seconds`` value from the specification.

    Returns:
        The accepted timeout in seconds, unchanged.

    Raises:
        ValueError: When the value is not an int, or falls outside the bounds.
    """
    timeout_seconds = _require_int(raw_field, WORKER_SPEC_TIMEOUT_KEY)
    if timeout_seconds < MIN_WORKER_TIMEOUT_SECONDS:
        raise ValueError(
            MINIMUM_WORKER_TIMEOUT_ERROR_TEMPLATE.format(
                field_name=WORKER_SPEC_TIMEOUT_KEY,
                requested_seconds=timeout_seconds,
                minimum_seconds=MIN_WORKER_TIMEOUT_SECONDS,
            )
        )
    if timeout_seconds > MAXIMUM_WORKER_TIMEOUT_SECONDS:
        raise ValueError(
            MAXIMUM_WORKER_TIMEOUT_ERROR_TEMPLATE.format(
                field_name=WORKER_SPEC_TIMEOUT_KEY,
                requested_seconds=timeout_seconds,
                maximum_seconds=MAXIMUM_WORKER_TIMEOUT_SECONDS,
            )
        )
    return timeout_seconds


def _parse_worker_entry(all_worker_fields: dict[str, object]) -> WorkerSpec:
    _require_known_worker_keys(all_worker_fields)
    role_name = _require_string(
        _require_worker_field(all_worker_fields, WORKER_SPEC_ROLE_NAME_KEY),
        WORKER_SPEC_ROLE_NAME_KEY,
    )
    all_prompt_parts = _require_worker_field(
        all_worker_fields, WORKER_SPEC_PROMPT_PARTS_KEY
    )
    working_directory = _require_string(
        _require_worker_field(all_worker_fields, WORKER_SPEC_CWD_KEY),
        WORKER_SPEC_CWD_KEY,
    )
    tool_profile = _require_string(
        _require_worker_field(all_worker_fields, WORKER_SPEC_TOOL_PROFILE_KEY),
        WORKER_SPEC_TOOL_PROFILE_KEY,
    )
    timeout_seconds = _require_timeout_within_bounds(
        all_worker_fields.get(
            WORKER_SPEC_TIMEOUT_KEY, DEFAULT_WORKER_TIMEOUT_SECONDS
        )
    )
    is_repo_only = _require_bool(
        all_worker_fields.get(WORKER_SPEC_IS_REPO_ONLY_KEY, False),
        WORKER_SPEC_IS_REPO_ONLY_KEY,
    )
    agent_name = all_worker_fields.get(WORKER_SPEC_AGENT_NAME_KEY)
    if not isinstance(all_prompt_parts, list) or not all_prompt_parts:
        raise ValueError("worker prompt_parts must be a non-empty list")
    if tool_profile not in ALL_KNOWN_TOOL_PROFILES:
        raise ValueError(f"unknown tool_profile: {tool_profile}")
    if agent_name is not None and not isinstance(agent_name, str):
        raise ValueError("worker agent_name must be a string or null")
    if isinstance(agent_name, str) and not agent_name:
        raise ValueError("worker agent_name must be non-empty or null")
    all_prompt_part_paths = tuple(
        Path(_require_string(each_part, WORKER_SPEC_PROMPT_PARTS_KEY))
        for each_part in all_prompt_parts
    )
    return WorkerSpec(
        role_name=role_name,
        all_prompt_part_paths=all_prompt_part_paths,
        working_directory=Path(working_directory),
        tool_profile=tool_profile,
        timeout_seconds=timeout_seconds,
        is_repo_only=is_repo_only,
        agent_name=agent_name,
    )


def load_batch_spec(specification_path: Path) -> BatchSpec:
    """Load and validate a JSON batch specification from disk.

    Args:
        specification_path: Path to the batch specification JSON file.

    Returns:
        The validated batch specification.

    Raises:
        ValueError: When the JSON shape is invalid, a required field is wrong,
            or a worker entry carries a key outside the accepted set.
        OSError: When the specification file cannot be read.
        json.JSONDecodeError: When the file is not valid JSON.
    """
    parsed_payload = json.loads(
        specification_path.read_text(encoding=UTF8_ENCODING)
    )
    if not isinstance(parsed_payload, dict):
        raise ValueError("batch specification must be a JSON object")
    role = parsed_payload.get(BATCH_SPEC_ROLE_KEY, DEFAULT_ROLE)
    should_ping = parsed_payload.get(BATCH_SPEC_SHOULD_PING_KEY, False)
    all_worker_entries = parsed_payload.get(BATCH_SPEC_WORKERS_KEY)
    if not isinstance(role, str):
        raise ValueError("batch role must be a string")
    if not isinstance(should_ping, bool):
        raise ValueError("batch should_ping must be a bool")
    if not isinstance(all_worker_entries, list) or not all_worker_entries:
        raise ValueError("batch workers must be a non-empty list")
    all_parsed_workers: list[WorkerSpec] = []
    for each_entry in all_worker_entries:
        if not isinstance(each_entry, dict):
            raise ValueError("each worker must be an object")
        all_parsed_workers.append(_parse_worker_entry(each_entry))
    advisor_spec = _parse_advisor_spec(parsed_payload.get(BATCH_SPEC_ADVISOR_KEY))
    return BatchSpec(
        role=role,
        should_ping=should_ping,
        all_workers=tuple(all_parsed_workers),
        advisor=advisor_spec,
    )


def _write_report_file(report_path: Path, report_text: str) -> None:
    report_path.write_text(report_text, encoding=UTF8_ENCODING)


def _report_text_from_outcome(outcome: GrokRunnerOutcome) -> str:
    if outcome.is_ok:
        return outcome.stdout or outcome.stderr
    all_present_streams = [
        each_stream
        for each_stream in (outcome.stdout, outcome.stderr)
        if each_stream
    ]
    return REPORT_STREAM_JOIN_SEPARATOR.join(all_present_streams)


def _mint_worker_scratch_paths(run_state_directory: Path) -> WorkerScratchPaths:
    return WorkerScratchPaths(
        prompt_path=_mint_worker_path(
            run_state_directory,
            prefix=PROMPT_FILENAME_PREFIX,
            suffix=PROMPT_FILENAME_SUFFIX,
        ),
        report_path=_mint_worker_path(
            run_state_directory,
            prefix=OUTPUT_FILENAME_PREFIX,
            suffix=OUTPUT_FILENAME_SUFFIX,
        ),
        leader_socket_path=_mint_worker_path(
            run_state_directory,
            prefix=LEADER_SOCKET_FILENAME_PREFIX,
            suffix=LEADER_SOCKET_FILENAME_SUFFIX,
        ),
        debug_path=_mint_worker_path(
            run_state_directory,
            prefix=DEBUG_FILENAME_PREFIX,
            suffix=DEBUG_FILENAME_SUFFIX,
        ),
    )


def _write_assembled_prompt(
    *,
    worker_spec: WorkerSpec,
    prompt_path: Path,
    advisor_session_id: str | None = None,
    advisor_spec: AdvisorSpec | None = None,
) -> None:
    prompt_text = assemble_worker_prompt(
        all_prompt_part_paths=worker_spec.all_prompt_part_paths,
        tool_profile=worker_spec.tool_profile,
    )
    if advisor_session_id is not None and advisor_spec is not None:
        header = ADVISOR_PROMPT_HEADER_TEMPLATE.format(
            session_id=advisor_session_id,
            model=advisor_spec.model,
            effort=advisor_spec.effort,
        )
        prompt_text = f"{header}{prompt_text}"
    prompt_path.write_text(prompt_text, encoding=UTF8_ENCODING)


def _invoke_worker(
    *,
    worker_spec: WorkerSpec,
    scratch_paths: WorkerScratchPaths,
    run_state_directory: Path,
) -> GrokRunnerOutcome:
    all_extra_arguments = build_tool_profile_arguments(
        tool_profile=worker_spec.tool_profile,
        is_repo_only=worker_spec.is_repo_only,
        debug_file=scratch_paths.debug_path,
    )
    return batch_headless_runner(
        prompt_file=scratch_paths.prompt_path,
        working_directory=worker_spec.working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=worker_spec.timeout_seconds,
        agent_name=worker_spec.agent_name,
        leader_socket_path=scratch_paths.leader_socket_path,
        all_extra_arguments=all_extra_arguments,
    )


def _worker_report(
    *,
    worker_spec: WorkerSpec,
    scratch_paths: WorkerScratchPaths,
    returncode: int,
    classification: str,
    is_ok: bool,
    report_text: str,
    advisor_session_id: str | None = None,
    advisor_completion_signal: str | None = None,
    advisor_launcher: str | None = None,
) -> WorkerReport:
    with suppress(OSError):
        _write_report_file(scratch_paths.report_path, report_text)
    return WorkerReport(
        role_name=worker_spec.role_name,
        tool_profile=worker_spec.tool_profile,
        returncode=returncode,
        classification=classification,
        is_ok=is_ok,
        report_text=report_text,
        report_path=str(scratch_paths.report_path),
        leader_socket=str(scratch_paths.leader_socket_path),
        prompt_path=str(scratch_paths.prompt_path),
        debug_path=str(scratch_paths.debug_path),
        advisor_session_id=advisor_session_id,
        advisor_completion_signal=advisor_completion_signal,
        advisor_launcher=advisor_launcher,
    )


def _build_worker_report(
    *,
    worker_spec: WorkerSpec,
    outcome: GrokRunnerOutcome,
    scratch_paths: WorkerScratchPaths,
) -> WorkerReport:
    return _worker_report(
        worker_spec=worker_spec,
        scratch_paths=scratch_paths,
        returncode=outcome.returncode,
        classification=outcome.classification,
        is_ok=outcome.is_ok,
        report_text=_report_text_from_outcome(outcome),
    )


def _error_report_for_exception(
    *,
    worker_spec: WorkerSpec,
    scratch_paths: WorkerScratchPaths,
    raised_exception: BaseException,
) -> WorkerReport:
    return _worker_report(
        worker_spec=worker_spec,
        scratch_paths=scratch_paths,
        returncode=WORKER_EXCEPTION_RETURN_CODE,
        classification=CLASSIFICATION_ERROR,
        is_ok=False,
        report_text=f"{type(raised_exception).__name__}: {raised_exception}",
    )



def _bind_worker_advisor_session(
    *,
    advisor_spec: AdvisorSpec,
    role_name: str,
    all_used_session_ids: set[str],
    session_id_lock: object | None,
) -> tuple[str, str]:
    if session_id_lock is not None:
        with session_id_lock:  # type: ignore[attr-defined]  # Lock protocol from threading.Lock
            return bind_unique_worker_advisor(
                advisor_spec=advisor_spec,
                role_name=role_name,
                all_used_session_ids=all_used_session_ids,
            )
    return bind_unique_worker_advisor(
        advisor_spec=advisor_spec,
        role_name=role_name,
        all_used_session_ids=all_used_session_ids,
    )


def _advisor_blocked_report(
    *,
    worker_spec: WorkerSpec,
    scratch_paths: WorkerScratchPaths,
    report_text: str,
    advisor_session_id: str | None = None,
    advisor_launcher: str | None = None,
) -> WorkerReport:
    return _worker_report(
        worker_spec=worker_spec,
        scratch_paths=scratch_paths,
        returncode=WORKER_EXCEPTION_RETURN_CODE,
        classification=CLASSIFICATION_ADVISOR_BLOCKED,
        is_ok=False,
        report_text=report_text,
        advisor_session_id=advisor_session_id,
        advisor_completion_signal=None,
        advisor_launcher=advisor_launcher,
    )



def _attach_advisor_completion_if_configured(
    *,
    worker_spec: WorkerSpec,
    scratch_paths: WorkerScratchPaths,
    worker_report: WorkerReport,
    advisor_spec: AdvisorSpec | None,
    advisor_session_id: str | None,
    advisor_launcher: str | None,
) -> WorkerReport:
    if advisor_spec is None or advisor_session_id is None:
        return worker_report
    try:
        completion_signal = obtain_advisor_completion_verdict(
            advisor_spec=advisor_spec,
            role_name=worker_spec.role_name,
            session_id=advisor_session_id,
            report_text=worker_report.report_text,
        )
    except ValueError as advisor_error:
        return _advisor_blocked_report(
            worker_spec=worker_spec,
            scratch_paths=scratch_paths,
            report_text=str(advisor_error),
            advisor_session_id=advisor_session_id,
            advisor_launcher=advisor_launcher,
        )
    return _worker_report(
        worker_spec=worker_spec,
        scratch_paths=scratch_paths,
        returncode=worker_report.returncode,
        classification=worker_report.classification,
        is_ok=worker_report.is_ok,
        report_text=worker_report.report_text,
        advisor_session_id=advisor_session_id,
        advisor_completion_signal=completion_signal,
        advisor_launcher=advisor_launcher,
    )


def _maybe_bind_advisor_for_worker(
    *,
    worker_spec: WorkerSpec,
    scratch_paths: WorkerScratchPaths,
    advisor_spec: AdvisorSpec | None,
    all_used_session_ids: set[str] | None,
    session_id_lock: object | None,
) -> tuple[str | None, str | None, WorkerReport | None]:
    if advisor_spec is None:
        return None, None, None
    used_ids = all_used_session_ids if all_used_session_ids is not None else set()
    advisor_session_id, pre_signal = _bind_worker_advisor_session(
        advisor_spec=advisor_spec,
        role_name=worker_spec.role_name,
        all_used_session_ids=used_ids,
        session_id_lock=session_id_lock,
    )
    if (
        advisor_session_id == PENDING_BIND_SENTINEL
        or pre_signal == PENDING_BIND_SENTINEL
    ):
        blocked = _advisor_blocked_report(
            worker_spec=worker_spec,
            scratch_paths=scratch_paths,
            report_text=f"{PENDING_BIND_SENTINEL} sentinel before launch",
            advisor_session_id=advisor_session_id,
            advisor_launcher=advisor_spec.launcher,
        )
        return advisor_session_id, advisor_spec.launcher, blocked
    return advisor_session_id, advisor_spec.launcher, None


def _map_launch_exception(
    *,
    worker_spec: WorkerSpec,
    scratch_paths: WorkerScratchPaths,
    raised_exception: BaseException,
    advisor_spec: AdvisorSpec | None,
    advisor_session_id: str | None,
    advisor_launcher: str | None,
) -> WorkerReport:
    if advisor_spec is not None and (
        isinstance(raised_exception, AdvisorFailureError)
        or PENDING_BIND_SENTINEL in str(raised_exception)
        or "advisor" in str(raised_exception).lower()
    ):
        return _advisor_blocked_report(
            worker_spec=worker_spec,
            scratch_paths=scratch_paths,
            report_text=f"{type(raised_exception).__name__}: {raised_exception}",
            advisor_session_id=advisor_session_id,
            advisor_launcher=advisor_launcher,
        )
    return _error_report_for_exception(
        worker_spec=worker_spec,
        scratch_paths=scratch_paths,
        raised_exception=raised_exception,
    )


def _run_worker_body(
    *,
    worker_spec: WorkerSpec,
    scratch_paths: WorkerScratchPaths,
    run_state_directory: Path,
    advisor_spec: AdvisorSpec | None,
    advisor_session_id: str | None,
    advisor_launcher: str | None,
) -> WorkerReport:
    _write_assembled_prompt(
        worker_spec=worker_spec,
        prompt_path=scratch_paths.prompt_path,
        advisor_session_id=advisor_session_id,
        advisor_spec=advisor_spec,
    )
    outcome = _invoke_worker(
        worker_spec=worker_spec,
        scratch_paths=scratch_paths,
        run_state_directory=run_state_directory,
    )
    worker_report = _build_worker_report(
        worker_spec=worker_spec,
        outcome=outcome,
        scratch_paths=scratch_paths,
    )
    return _attach_advisor_completion_if_configured(
        worker_spec=worker_spec,
        scratch_paths=scratch_paths,
        worker_report=worker_report,
        advisor_spec=advisor_spec,
        advisor_session_id=advisor_session_id,
        advisor_launcher=advisor_launcher,
    )


def _launch_one_worker(
    *,
    worker_spec: WorkerSpec,
    worker_index: int,
    run_state_directory: Path,
    advisor_spec: AdvisorSpec | None = None,
    all_used_session_ids: set[str] | None = None,
    session_id_lock: object | None = None,
) -> WorkerReport:
    batch_sleep(worker_index * WORKER_STAGGER_SECONDS)
    scratch_paths = _mint_worker_scratch_paths(run_state_directory)
    advisor_session_id: str | None = None
    advisor_launcher: str | None = None
    try:
        (
            advisor_session_id,
            advisor_launcher,
            early_block,
        ) = _maybe_bind_advisor_for_worker(
            worker_spec=worker_spec,
            scratch_paths=scratch_paths,
            advisor_spec=advisor_spec,
            all_used_session_ids=all_used_session_ids,
            session_id_lock=session_id_lock,
        )
        if early_block is not None:
            return early_block
        return _run_worker_body(
            worker_spec=worker_spec,
            scratch_paths=scratch_paths,
            run_state_directory=run_state_directory,
            advisor_spec=advisor_spec,
            advisor_session_id=advisor_session_id,
            advisor_launcher=advisor_launcher,
        )
    except (
        OSError,
        ValueError,
        RuntimeError,
        TypeError,
        AttributeError,
        LookupError,
        AdvisorFailureError,
    ) as raised_exception:
        return _map_launch_exception(
            worker_spec=worker_spec,
            scratch_paths=scratch_paths,
            raised_exception=raised_exception,
            advisor_spec=advisor_spec,
            advisor_session_id=advisor_session_id,
            advisor_launcher=advisor_launcher,
        )



def run_grok_batch(
    *,
    batch_spec: BatchSpec,
    run_state_directory: Path,
) -> BatchSummary:
    """Gate with preflight, launch all workers staggered, collect reports.

    Args:
        batch_spec: Validated batch specification.
        run_state_directory: Run-scoped directory for sockets, prompts, reports.

    Returns:
        The batch summary including preflight status and per-worker reports.
    """
    run_state_directory.mkdir(parents=True, exist_ok=True)
    preflight_outcome: PreflightOutcome = batch_preflight(
        role=batch_spec.role,
        should_ping=batch_spec.should_ping,
        run_state_directory=run_state_directory,
    )
    if not preflight_outcome.is_usable:
        return BatchSummary(
            is_preflight_usable=False,
            preflight_reason=preflight_outcome.reason,
            all_worker_reports=(),
        )
    worker_count = len(batch_spec.all_workers)
    if not worker_count:
        return BatchSummary(
            is_preflight_usable=True,
            preflight_reason=None,
            all_worker_reports=(),
        )
    all_used_session_ids: set[str] = set()
    session_id_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        all_futures = [
            executor.submit(
                _launch_one_worker,
                worker_spec=each_worker,
                worker_index=each_index,
                run_state_directory=run_state_directory,
                advisor_spec=batch_spec.advisor,
                all_used_session_ids=all_used_session_ids,
                session_id_lock=session_id_lock,
            )
            for each_index, each_worker in enumerate(batch_spec.all_workers)
        ]
        all_worker_reports = tuple(
            each_future.result() for each_future in all_futures
        )
    return BatchSummary(
        is_preflight_usable=True,
        preflight_reason=None,
        all_worker_reports=all_worker_reports,
    )


def batch_summary_as_dict(batch_summary: BatchSummary) -> dict[str, object]:
    """Convert a batch summary into the stdout JSON object shape.

    Args:
        batch_summary: The summary returned by ``run_grok_batch``.

    Returns:
        A JSON-serializable dictionary matching the batch summary contract.
    """
    all_worker_payloads = [
        {
            SUMMARY_ROLE_NAME_KEY: each_report.role_name,
            SUMMARY_TOOL_PROFILE_KEY: each_report.tool_profile,
            SUMMARY_RETURNCODE_KEY: each_report.returncode,
            SUMMARY_CLASSIFICATION_KEY: each_report.classification,
            SUMMARY_IS_OK_KEY: each_report.is_ok,
            SUMMARY_REPORT_TEXT_KEY: each_report.report_text,
            SUMMARY_OUTPUT_FILE_KEY: each_report.report_path,
            SUMMARY_LEADER_SOCKET_KEY: each_report.leader_socket,
            SUMMARY_PROMPT_FILE_KEY: each_report.prompt_path,
            SUMMARY_DEBUG_FILE_KEY: each_report.debug_path,
            SUMMARY_ADVISOR_SESSION_ID_KEY: each_report.advisor_session_id,
            SUMMARY_ADVISOR_SIGNAL_KEY: each_report.advisor_completion_signal,
            SUMMARY_ADVISOR_LAUNCHER_KEY: each_report.advisor_launcher,
        }
        for each_report in batch_summary.all_worker_reports
    ]
    return {
        SUMMARY_IS_PREFLIGHT_USABLE_KEY: batch_summary.is_preflight_usable,
        SUMMARY_PREFLIGHT_REASON_KEY: batch_summary.preflight_reason,
        SUMMARY_WORKERS_KEY: all_worker_payloads,
    }


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Launch a fleet of headless grok workers and emit a batch summary."
        )
    )
    parser.add_argument(
        CLI_BATCH_SPEC_FLAG,
        dest="specification_path",
        required=True,
        type=Path,
        help="Path to the JSON batch specification file.",
    )
    parser.add_argument(
        CLI_RUN_STATE_DIR_FLAG,
        dest="run_state_directory",
        required=True,
        type=Path,
        help="Run-scoped state directory for sockets, prompts, and reports.",
    )
    return parser


def main(all_command_arguments: list[str]) -> int:
    """Run the batch launcher for CLI arguments and print the summary JSON.

    An unreadable, malformed, or invalid specification, and a run state
    directory that cannot be created, each print one diagnostic line on stderr
    and exit ``1`` rather than raising out of the CLI.

    Args:
        all_command_arguments: The argument vector after the program name.

    Returns:
        ``0`` when preflight is usable and every worker is ok; ``1`` otherwise.
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_command_arguments)
    try:
        batch_spec = load_batch_spec(parsed_arguments.specification_path)
        batch_summary = run_grok_batch(
            batch_spec=batch_spec,
            run_state_directory=parsed_arguments.run_state_directory,
        )
    except (OSError, ValueError) as launch_error:
        print(
            f"{BATCH_LAUNCH_ERROR_STDERR_PREFIX}{launch_error}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(batch_summary_as_dict(batch_summary)))
    if not batch_summary.is_preflight_usable:
        return 1
    if not all(each_report.is_ok for each_report in batch_summary.all_worker_reports):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
