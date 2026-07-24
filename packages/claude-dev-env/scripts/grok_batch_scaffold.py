#!/usr/bin/env python3
"""Scaffold the deterministic part files and batch-spec skeleton for a grok fleet.

::

    python grok_batch_scaffold.py --run-temp-dir <dir> \\
        --worker map-callsites:readonly --worker fix-timeout:build
    writes: <dir>/report-contract.md, <dir>/map-callsites.brief.md,
            <dir>/map-callsites.task.md, ... , <dir>/batch-spec.json

Each worker's ``prompt_parts`` is wired to its brief, its task body, and the
one shared report contract. The caller fills the task-body files and the
``cwd`` placeholder, then launches the spec with ``spawn_grok_batch.py``.
Import ``scaffold_batch`` for the outcome object, or run the module as a CLI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dev_env_scripts_constants.grok_scaffold_constants import (
    BATCH_SPEC_FILENAME,
    BRIEF_FILENAME_SUFFIX,
    BUILD_BRIEF_TEMPLATE,
    CLI_WORKER_FLAG,
    CWD_PLACEHOLDER,
    DEFAULT_IS_REPO_ONLY,
    DEFAULT_SHOULD_PING,
    JSON_INDENT,
    READONLY_BRIEF_TEMPLATE,
    REPORT_CONTRACT_FILENAME,
    REPORT_CONTRACT_TEMPLATE,
    ROLE_NAME_PATTERN,
    SCAFFOLD_ERROR_STDERR_PREFIX,
    SCAFFOLD_RESULT_REPORT_CONTRACT_FILE_KEY,
    SCAFFOLD_RESULT_SPEC_FILE_KEY,
    SCAFFOLD_RESULT_WORKERS_KEY,
    SCAFFOLD_WORKER_BRIEF_FILE_KEY,
    SCAFFOLD_WORKER_ROLE_NAME_KEY,
    SCAFFOLD_WORKER_TASK_BODY_FILE_KEY,
    TASK_BODY_FILENAME_SUFFIX,
    TASK_BODY_TEMPLATE,
    WORKER_TOKEN_SEPARATOR,
)
from dev_env_scripts_constants.grok_worker_constants import (
    ALL_KNOWN_TOOL_PROFILES,
    BATCH_SPEC_ROLE_KEY,
    BATCH_SPEC_SHOULD_PING_KEY,
    BATCH_SPEC_WORKERS_KEY,
    CLI_ROLE_FLAG,
    CLI_RUN_STATE_DIR_FLAG,
    DEFAULT_ROLE,
    DEFAULT_WORKER_MAX_TURNS,
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    TOOL_PROFILE_READONLY,
    UTF8_ENCODING,
    WORKER_SPEC_AGENT_NAME_KEY,
    WORKER_SPEC_CWD_KEY,
    WORKER_SPEC_IS_REPO_ONLY_KEY,
    WORKER_SPEC_MAX_TURNS_KEY,
    WORKER_SPEC_PROMPT_PARTS_KEY,
    WORKER_SPEC_ROLE_NAME_KEY,
    WORKER_SPEC_TIMEOUT_KEY,
    WORKER_SPEC_TOOL_PROFILE_KEY,
)


@dataclass(frozen=True)
class ScaffoldWorker:
    """One worker to scaffold: a role-name slug and a tool profile."""

    role_name: str
    tool_profile: str


@dataclass(frozen=True)
class ScaffoldedWorkerPaths:
    """The brief and task-body part paths written for one worker."""

    role_name: str
    tool_profile: str
    brief_path: Path
    task_body_path: Path


@dataclass(frozen=True)
class ScaffoldOutcome:
    """The batch-spec skeleton, shared report contract, and per-worker paths."""

    spec_path: Path
    report_contract_path: Path
    all_worker_paths: tuple[ScaffoldedWorkerPaths, ...]


def _brief_template_for_profile(tool_profile: str) -> str:
    if tool_profile == TOOL_PROFILE_READONLY:
        return READONLY_BRIEF_TEMPLATE
    return BUILD_BRIEF_TEMPLATE


def parse_worker_token(worker_token: str) -> ScaffoldWorker:
    """Parse one ``role_name:profile`` CLI token into a worker.

    Args:
        worker_token: A ``role_name:profile`` pair; role_name a lowercase
            slug, profile ``readonly`` or ``build``.

    Returns:
        The parsed worker.

    Raises:
        ValueError: On a missing separator, a non-slug role name, or an
            unknown tool profile.
    """
    if WORKER_TOKEN_SEPARATOR not in worker_token:
        raise ValueError(
            f"worker must be role_name{WORKER_TOKEN_SEPARATOR}profile: {worker_token}"
        )
    role_name, _, tool_profile = worker_token.partition(WORKER_TOKEN_SEPARATOR)
    if re.match(ROLE_NAME_PATTERN, role_name) is None:
        raise ValueError(f"worker role_name must be a slug: {role_name}")
    if tool_profile not in ALL_KNOWN_TOOL_PROFILES:
        raise ValueError(f"unknown tool_profile: {tool_profile}")
    return ScaffoldWorker(role_name=role_name, tool_profile=tool_profile)


def _worker_spec_entry(
    *,
    worker: ScaffoldWorker,
    brief_path: Path,
    task_body_path: Path,
    report_contract_path: Path,
) -> dict[str, object]:
    return {
        WORKER_SPEC_ROLE_NAME_KEY: worker.role_name,
        WORKER_SPEC_PROMPT_PARTS_KEY: [
            str(brief_path),
            str(task_body_path),
            str(report_contract_path),
        ],
        WORKER_SPEC_CWD_KEY: CWD_PLACEHOLDER,
        WORKER_SPEC_TOOL_PROFILE_KEY: worker.tool_profile,
        WORKER_SPEC_TIMEOUT_KEY: DEFAULT_WORKER_TIMEOUT_SECONDS,
        WORKER_SPEC_IS_REPO_ONLY_KEY: DEFAULT_IS_REPO_ONLY,
        WORKER_SPEC_MAX_TURNS_KEY: DEFAULT_WORKER_MAX_TURNS,
        WORKER_SPEC_AGENT_NAME_KEY: None,
    }


def _scaffold_one_worker(
    *,
    worker: ScaffoldWorker,
    run_state_directory: Path,
    report_contract_path: Path,
) -> tuple[ScaffoldedWorkerPaths, dict[str, object]]:
    brief_path = run_state_directory / f"{worker.role_name}{BRIEF_FILENAME_SUFFIX}"
    task_body_path = (
        run_state_directory / f"{worker.role_name}{TASK_BODY_FILENAME_SUFFIX}"
    )
    brief_path.write_text(
        _brief_template_for_profile(worker.tool_profile), encoding=UTF8_ENCODING
    )
    task_body_path.write_text(TASK_BODY_TEMPLATE, encoding=UTF8_ENCODING)
    scaffolded_paths = ScaffoldedWorkerPaths(
        role_name=worker.role_name,
        tool_profile=worker.tool_profile,
        brief_path=brief_path,
        task_body_path=task_body_path,
    )
    worker_entry = _worker_spec_entry(
        worker=worker,
        brief_path=brief_path,
        task_body_path=task_body_path,
        report_contract_path=report_contract_path,
    )
    return scaffolded_paths, worker_entry


def _scaffold_all_workers(
    *,
    all_workers: tuple[ScaffoldWorker, ...],
    run_state_directory: Path,
    report_contract_path: Path,
) -> tuple[list[ScaffoldedWorkerPaths], list[dict[str, object]]]:
    all_worker_paths: list[ScaffoldedWorkerPaths] = []
    all_worker_entries: list[dict[str, object]] = []
    for each_worker in all_workers:
        scaffolded_paths, worker_entry = _scaffold_one_worker(
            worker=each_worker,
            run_state_directory=run_state_directory,
            report_contract_path=report_contract_path,
        )
        all_worker_paths.append(scaffolded_paths)
        all_worker_entries.append(worker_entry)
    return all_worker_paths, all_worker_entries


def _write_report_contract(run_state_directory: Path) -> Path:
    run_state_directory.mkdir(parents=True, exist_ok=True)
    report_contract_path = run_state_directory / REPORT_CONTRACT_FILENAME
    report_contract_path.write_text(REPORT_CONTRACT_TEMPLATE, encoding=UTF8_ENCODING)
    return report_contract_path


def _write_batch_spec(
    *,
    run_state_directory: Path,
    role: str,
    all_worker_entries: list[dict[str, object]],
) -> Path:
    spec_payload = {
        BATCH_SPEC_ROLE_KEY: role,
        BATCH_SPEC_SHOULD_PING_KEY: DEFAULT_SHOULD_PING,
        BATCH_SPEC_WORKERS_KEY: all_worker_entries,
    }
    spec_path = run_state_directory / BATCH_SPEC_FILENAME
    spec_path.write_text(
        json.dumps(spec_payload, indent=JSON_INDENT), encoding=UTF8_ENCODING
    )
    return spec_path


def scaffold_batch(
    *, run_state_directory: Path, all_workers: tuple[ScaffoldWorker, ...], role: str
) -> ScaffoldOutcome:
    """Write the report contract, per-worker parts, and batch-spec skeleton.

    Args:
        run_state_directory: Run-scoped directory that receives every file.
        all_workers: The workers to scaffold, in batch order.
        role: Preflight role recorded on the batch spec.

    Returns:
        The batch-spec, report-contract, and per-worker part paths.
    """
    report_contract_path = _write_report_contract(run_state_directory)
    all_worker_paths, all_worker_entries = _scaffold_all_workers(
        all_workers=all_workers,
        run_state_directory=run_state_directory,
        report_contract_path=report_contract_path,
    )
    spec_path = _write_batch_spec(
        run_state_directory=run_state_directory,
        role=role,
        all_worker_entries=all_worker_entries,
    )
    return ScaffoldOutcome(
        spec_path=spec_path,
        report_contract_path=report_contract_path,
        all_worker_paths=tuple(all_worker_paths),
    )


def scaffold_outcome_as_dict(scaffold_outcome: ScaffoldOutcome) -> dict[str, object]:
    """Convert a scaffold outcome into the stdout JSON object shape.

    Args:
        scaffold_outcome: The outcome returned by ``scaffold_batch``.

    Returns:
        A JSON-serializable dictionary of the written paths.
    """
    all_worker_rows = [
        {
            SCAFFOLD_WORKER_ROLE_NAME_KEY: each_scaffolded.role_name,
            SCAFFOLD_WORKER_BRIEF_FILE_KEY: str(each_scaffolded.brief_path),
            SCAFFOLD_WORKER_TASK_BODY_FILE_KEY: str(each_scaffolded.task_body_path),
        }
        for each_scaffolded in scaffold_outcome.all_worker_paths
    ]
    return {
        SCAFFOLD_RESULT_SPEC_FILE_KEY: str(scaffold_outcome.spec_path),
        SCAFFOLD_RESULT_REPORT_CONTRACT_FILE_KEY: str(
            scaffold_outcome.report_contract_path
        ),
        SCAFFOLD_RESULT_WORKERS_KEY: all_worker_rows,
    }


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scaffold worker part files and a batch-spec skeleton for a grok fleet."
        )
    )
    parser.add_argument(
        CLI_RUN_STATE_DIR_FLAG,
        dest="run_state_directory",
        required=True,
        type=Path,
        help="Run-scoped directory that receives the scaffolded files.",
    )
    parser.add_argument(
        CLI_WORKER_FLAG,
        dest="all_worker_tokens",
        action="append",
        required=True,
        metavar="ROLE_NAME:PROFILE",
        help="One worker as role_name:profile (readonly or build). Repeatable.",
    )
    parser.add_argument(
        CLI_ROLE_FLAG,
        dest="role",
        default=DEFAULT_ROLE,
        help="Preflight role recorded on the batch spec.",
    )
    return parser


def main(all_command_arguments: list[str]) -> int:
    """Scaffold from CLI arguments and write the summary JSON to stdout.

    A bad worker token or an uncreatable run directory writes one stderr line
    and exits ``1`` before any file is written.

    Args:
        all_command_arguments: The argument vector after the program name.

    Returns:
        ``0`` on success; ``1`` on a bad argument or a write failure.
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_command_arguments)
    try:
        all_workers = tuple(
            parse_worker_token(each_token)
            for each_token in parsed_arguments.all_worker_tokens
        )
        scaffold_outcome = scaffold_batch(
            run_state_directory=parsed_arguments.run_state_directory,
            all_workers=all_workers,
            role=parsed_arguments.role,
        )
    except (OSError, ValueError) as scaffold_error:
        sys.stderr.write(f"{SCAFFOLD_ERROR_STDERR_PREFIX}{scaffold_error}\n")
        return 1
    sys.stdout.write(json.dumps(scaffold_outcome_as_dict(scaffold_outcome)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
