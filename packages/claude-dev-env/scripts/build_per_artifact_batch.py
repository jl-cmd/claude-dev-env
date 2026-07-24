#!/usr/bin/env python3
"""Emit a grok batch-spec JSON for a per-artifact fan-out fleet.

Builds one ``build`` worker per artifact so the lead never hand-writes the
batch specification. Each worker receives the shared brief plus that artifact's
evidence file as ordered prompt parts.

Import ``build_per_artifact_batch`` for the dict, or run as a CLI::

    python build_per_artifact_batch.py \\
      --brief /abs/brief.md \\
      --cwd /abs/worktree \\
      --artifact notes-a=/abs/evidence-a.md \\
      --artifact notes-b=/abs/evidence-b.md \\
      --out /abs/run/per_artifact_batch.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from dev_env_scripts_constants.build_per_artifact_batch_constants import (
    ARTIFACT_ROLE_PATH_SEPARATOR,
    CLI_ARTIFACT_FLAG,
    CLI_BRIEF_FLAG,
    CLI_CWD_FLAG,
    CLI_MAX_TURNS_FLAG,
    CLI_OUT_FLAG,
    CLI_ROLE_FLAG,
    CLI_TIMEOUT_SECONDS_FLAG,
    CLI_TOOL_PROFILE_FLAG,
    DEFAULT_OUT_FILENAME,
    DEFAULT_ROLE,
    DEFAULT_SHOULD_PING,
    DEFAULT_WORKER_MAX_TURNS,
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    EXIT_FAILURE,
    EXIT_SUCCESS,
    JSON_INDENT_SPACES,
    STDERR_ERROR_PREFIX,
    TOOL_PROFILE_BUILD,
    UTF8_ENCODING,
)
from dev_env_scripts_constants.grok_worker_constants import (
    BATCH_SPEC_ROLE_KEY,
    BATCH_SPEC_SHOULD_PING_KEY,
    BATCH_SPEC_WORKERS_KEY,
    WORKER_SPEC_AGENT_NAME_KEY,
    WORKER_SPEC_CWD_KEY,
    WORKER_SPEC_IS_REPO_ONLY_KEY,
    WORKER_SPEC_MAX_TURNS_KEY,
    WORKER_SPEC_PROMPT_PARTS_KEY,
    WORKER_SPEC_ROLE_NAME_KEY,
    WORKER_SPEC_TIMEOUT_KEY,
    WORKER_SPEC_TOOL_PROFILE_KEY,
)


class BatchBuildError(Exception):
    """Raised when the brief, evidence, or artifact list cannot form a batch."""


def build_per_artifact_batch(
    *,
    brief_path: str | Path,
    all_artifacts: Sequence[tuple[str, str | Path]],
    cwd: str | Path,
    tool_profile: str = TOOL_PROFILE_BUILD,
    timeout_seconds: int = DEFAULT_WORKER_TIMEOUT_SECONDS,
    max_turns: int = DEFAULT_WORKER_MAX_TURNS,
    role: str = DEFAULT_ROLE,
) -> dict[str, object]:
    """Build a deterministic per-artifact grok batch-spec dictionary.

    ::

        build_per_artifact_batch(
            brief_path=brief.md,
            all_artifacts=[("a", evidence_a.md), ("b", evidence_b.md)],
            cwd=worktree,
        )
        ok: two workers, each prompt_parts = [brief, that evidence]
        flag: an empty artifact list or a missing evidence file raises
            BatchBuildError

    Args:
        brief_path: Shared per-artifact brief file every worker receives first.
        all_artifacts: Ordered ``(role_name, evidence_path)`` pairs, one per
            worker.
        cwd: Working directory assigned to every worker.
        tool_profile: Tool profile name (default ``build``).
        timeout_seconds: Per-worker timeout in seconds.
        max_turns: Per-worker max-turns cap.
        role: Preflight role on the batch specification.

    Returns:
        A batch-spec dict ready for ``json.dump`` or ``load_batch_spec``.

    Raises:
        BatchBuildError: When ``all_artifacts`` is empty, the brief is
            missing, or any evidence path is not an existing file.
    """
    if not all_artifacts:
        raise BatchBuildError("artifacts must be a non-empty sequence")
    resolved_brief = _require_existing_file(brief_path, "brief_path")
    resolved_cwd = str(Path(cwd).resolve())
    all_workers: list[dict[str, object]] = []
    for each_role_name, each_evidence_path in all_artifacts:
        resolved_evidence = _require_existing_file(
            each_evidence_path, f"evidence for role {each_role_name!r}"
        )
        all_workers.append(
            {
                WORKER_SPEC_ROLE_NAME_KEY: each_role_name,
                WORKER_SPEC_PROMPT_PARTS_KEY: [
                    resolved_brief,
                    resolved_evidence,
                ],
                WORKER_SPEC_CWD_KEY: resolved_cwd,
                WORKER_SPEC_TOOL_PROFILE_KEY: tool_profile,
                WORKER_SPEC_TIMEOUT_KEY: timeout_seconds,
                WORKER_SPEC_IS_REPO_ONLY_KEY: False,
                WORKER_SPEC_MAX_TURNS_KEY: max_turns,
                WORKER_SPEC_AGENT_NAME_KEY: None,
            }
        )
    return {
        BATCH_SPEC_ROLE_KEY: role,
        BATCH_SPEC_SHOULD_PING_KEY: DEFAULT_SHOULD_PING,
        BATCH_SPEC_WORKERS_KEY: all_workers,
    }


def _require_existing_file(file_path: str | Path, label: str) -> str:
    resolved_path = Path(file_path).resolve()
    if not resolved_path.is_file():
        raise BatchBuildError(f"{label} is not an existing file: {resolved_path}")
    return str(resolved_path)


def _parse_artifact_argument(artifact_argument: str) -> tuple[str, str]:
    if ARTIFACT_ROLE_PATH_SEPARATOR not in artifact_argument:
        raise BatchBuildError(
            f"artifact must be ROLE_NAME{ARTIFACT_ROLE_PATH_SEPARATOR}EVIDENCE_PATH; "
            f"got: {artifact_argument!r}"
        )
    role_name, evidence_path = artifact_argument.split(
        ARTIFACT_ROLE_PATH_SEPARATOR, maxsplit=1
    )
    if not role_name or not evidence_path:
        raise BatchBuildError(
            f"artifact must be ROLE_NAME{ARTIFACT_ROLE_PATH_SEPARATOR}EVIDENCE_PATH; "
            f"got: {artifact_argument!r}"
        )
    return role_name, evidence_path


def _write_batch_spec(
    all_batch_specification_fields: Mapping[str, object], out_path: Path
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(all_batch_specification_fields, indent=JSON_INDENT_SPACES) + "\n",
        encoding=UTF8_ENCODING,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Emit a grok batch-spec JSON with one build worker per artifact.")
    )
    parser.add_argument(
        CLI_BRIEF_FLAG,
        required=True,
        help="Path to the shared per-artifact brief file.",
    )
    parser.add_argument(
        CLI_CWD_FLAG,
        required=True,
        help="Working directory every worker receives.",
    )
    parser.add_argument(
        CLI_OUT_FLAG,
        default=None,
        help=(f"Path for the batch-spec JSON (default: <cwd>/{DEFAULT_OUT_FILENAME})."),
    )
    parser.add_argument(
        CLI_ARTIFACT_FLAG,
        action="append",
        required=True,
        metavar="ROLE_NAME=EVIDENCE_PATH",
        help="One ROLE_NAME=EVIDENCE_PATH pair (repeatable, at least one).",
    )
    parser.add_argument(
        CLI_TOOL_PROFILE_FLAG,
        default=TOOL_PROFILE_BUILD,
        help=f"Tool profile for every worker (default: {TOOL_PROFILE_BUILD}).",
    )
    parser.add_argument(
        CLI_TIMEOUT_SECONDS_FLAG,
        type=int,
        default=DEFAULT_WORKER_TIMEOUT_SECONDS,
        help=(
            "Per-worker timeout in seconds "
            f"(default: {DEFAULT_WORKER_TIMEOUT_SECONDS})."
        ),
    )
    parser.add_argument(
        CLI_MAX_TURNS_FLAG,
        type=int,
        default=DEFAULT_WORKER_MAX_TURNS,
        help=f"Per-worker max turns (default: {DEFAULT_WORKER_MAX_TURNS}).",
    )
    parser.add_argument(
        CLI_ROLE_FLAG,
        default=DEFAULT_ROLE,
        help=(
            "Preflight role recorded on the batch specification "
            f"(default: {DEFAULT_ROLE})."
        ),
    )
    return parser


def _build_and_write_batch_spec(parsed_arguments: argparse.Namespace) -> Path:
    all_artifacts = [
        _parse_artifact_argument(each_artifact_argument)
        for each_artifact_argument in parsed_arguments.artifact
    ]
    batch_spec = build_per_artifact_batch(
        brief_path=parsed_arguments.brief,
        all_artifacts=all_artifacts,
        cwd=parsed_arguments.cwd,
        tool_profile=parsed_arguments.tool_profile,
        timeout_seconds=parsed_arguments.timeout_seconds,
        max_turns=parsed_arguments.max_turns,
        role=parsed_arguments.role,
    )
    resolved_cwd = Path(parsed_arguments.cwd).resolve()
    out_path = (
        Path(parsed_arguments.out).resolve()
        if parsed_arguments.out is not None
        else (resolved_cwd / DEFAULT_OUT_FILENAME).resolve()
    )
    _write_batch_spec(batch_spec, out_path)
    return out_path


def main(all_command_arguments: list[str]) -> int:
    """Parse CLI args, emit the batch-spec JSON, and print the out path.

    Args:
        all_command_arguments: Argument tokens after the script name.

    Returns:
        ``0`` on success, ``1`` when validation fails.
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_command_arguments)
    try:
        out_path = _build_and_write_batch_spec(parsed_arguments)
    except BatchBuildError as batch_error:
        print(f"{STDERR_ERROR_PREFIX}{batch_error}", file=sys.stderr)
        return EXIT_FAILURE
    print(out_path)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
