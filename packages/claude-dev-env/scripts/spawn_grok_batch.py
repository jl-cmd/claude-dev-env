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
import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from dev_env_scripts_constants.grok_worker_constants import (
    ALL_KNOWN_TOOL_PROFILES,
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
    DEFAULT_WORKER_MAX_TURNS,
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    DISABLE_WEB_SEARCH_FLAG,
    DISALLOWED_TOOLS_FLAG,
    LEADER_SOCKET_FILENAME_PREFIX,
    LEADER_SOCKET_FILENAME_SUFFIX,
    MIN_WORKER_MAX_TURNS,
    MIN_WORKER_TIMEOUT_SECONDS,
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
    UTF8_ENCODING,
    WORKER_EXCEPTION_RETURN_CODE,
    WORKER_SPEC_AGENT_NAME_KEY,
    WORKER_SPEC_CWD_KEY,
    WORKER_SPEC_IS_REPO_ONLY_KEY,
    WORKER_SPEC_MAX_TURNS_KEY,
    WORKER_SPEC_PROMPT_PARTS_KEY,
    WORKER_SPEC_ROLE_NAME_KEY,
    WORKER_SPEC_TIMEOUT_KEY,
    WORKER_SPEC_TOOL_PROFILE_KEY,
)
from dev_env_scripts_constants.timing import WORKER_STAGGER_SECONDS
from grok_headless_runner import GrokRunnerOutcome, run_headless_worker
from grok_worker_preflight import PreflightOutcome, run_preflight

batch_sleep = time.sleep
batch_headless_runner = run_headless_worker
batch_preflight = run_preflight


@dataclass(frozen=True)
class WorkerSpec:
    """One worker entry from a batch specification."""

    role_name: str
    all_prompt_part_paths: tuple[Path, ...]
    working_directory: Path
    tool_profile: str
    timeout_seconds: int
    is_repo_only: bool = False
    max_turns: int = DEFAULT_WORKER_MAX_TURNS
    agent_name: str | None = None


@dataclass(frozen=True)
class BatchSpec:
    """Full batch specification for one fleet launch."""

    role: str
    should_ping: bool
    all_workers: tuple[WorkerSpec, ...]


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


def _require_int_at_least(
    raw_field: object, field_name: str, minimum_accepted: int
) -> int:
    parsed_integer = _require_int(raw_field, field_name)
    if parsed_integer < minimum_accepted:
        raise ValueError(
            f"worker {field_name} must be >= {minimum_accepted}"
        )
    return parsed_integer


def _parse_worker_entry(all_worker_fields: dict[str, object]) -> WorkerSpec:
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
    timeout_seconds = _require_int_at_least(
        all_worker_fields.get(
            WORKER_SPEC_TIMEOUT_KEY, DEFAULT_WORKER_TIMEOUT_SECONDS
        ),
        WORKER_SPEC_TIMEOUT_KEY,
        MIN_WORKER_TIMEOUT_SECONDS,
    )
    is_repo_only = _require_bool(
        all_worker_fields.get(WORKER_SPEC_IS_REPO_ONLY_KEY, False),
        WORKER_SPEC_IS_REPO_ONLY_KEY,
    )
    max_turns = _require_int_at_least(
        all_worker_fields.get(WORKER_SPEC_MAX_TURNS_KEY, DEFAULT_WORKER_MAX_TURNS),
        WORKER_SPEC_MAX_TURNS_KEY,
        MIN_WORKER_MAX_TURNS,
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
        max_turns=max_turns,
        agent_name=agent_name,
    )


def load_batch_spec(specification_path: Path) -> BatchSpec:
    """Load and validate a JSON batch specification from disk.

    Args:
        specification_path: Path to the batch specification JSON file.

    Returns:
        The validated batch specification.

    Raises:
        ValueError: When the JSON shape is invalid or a required field is wrong.
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
    return BatchSpec(
        role=role,
        should_ping=should_ping,
        all_workers=tuple(all_parsed_workers),
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
) -> None:
    prompt_text = assemble_worker_prompt(
        all_prompt_part_paths=worker_spec.all_prompt_part_paths,
        tool_profile=worker_spec.tool_profile,
    )
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
        max_turns=worker_spec.max_turns,
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


def _launch_one_worker(
    *,
    worker_spec: WorkerSpec,
    worker_index: int,
    run_state_directory: Path,
) -> WorkerReport:
    batch_sleep(worker_index * WORKER_STAGGER_SECONDS)
    scratch_paths = _mint_worker_scratch_paths(run_state_directory)
    try:
        _write_assembled_prompt(
            worker_spec=worker_spec,
            prompt_path=scratch_paths.prompt_path,
        )
        outcome = _invoke_worker(
            worker_spec=worker_spec,
            scratch_paths=scratch_paths,
            run_state_directory=run_state_directory,
        )
        return _build_worker_report(
            worker_spec=worker_spec,
            outcome=outcome,
            scratch_paths=scratch_paths,
        )
    except (
        OSError,
        ValueError,
        RuntimeError,
        TypeError,
        AttributeError,
        LookupError,
    ) as raised_exception:
        return _error_report_for_exception(
            worker_spec=worker_spec,
            scratch_paths=scratch_paths,
            raised_exception=raised_exception,
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
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        all_futures = [
            executor.submit(
                _launch_one_worker,
                worker_spec=each_worker,
                worker_index=each_index,
                run_state_directory=run_state_directory,
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
