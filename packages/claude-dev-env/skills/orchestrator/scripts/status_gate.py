#!/usr/bin/env python3
"""Deterministic orchestrator status gate: status JSON and reschedule exit codes.

::

    python status_gate.py set --status-file PATH --status active|done
    python status_gate.py should-reschedule --status-file PATH

``should-reschedule`` exits 0 only when the status file exists and
``status`` is ``active``. Any other case exits 1 (stop the refresh loop).
Missing or invalid status files fail closed (do not reschedule).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from status_gate_constants.config.constants import (
    ALL_COMMANDS,
    ALL_DEFAULT_STATUS_DIRECTORY_PARTS,
    ALL_VALID_RUN_STATUSES,
    COMMAND_SET,
    COMMAND_SHOULD_RESCHEDULE,
    EXIT_CODE_STOP,
    EXIT_CODE_SUCCESS,
    EXIT_CODE_USAGE_ERROR,
    JSON_INDENT_SPACES,
    REASON_ACTIVE,
    REASON_FIELD_NAME,
    REASON_INVALID_STATUS_FILE,
    REASON_MISSING_STATUS_FILE,
    REASON_STATUS_NOT_ACTIVE,
    RESCHEDULE_FIELD_NAME,
    RUN_SLUG_ENV_VAR,
    RUN_SLUG_FIELD_NAME,
    RUN_STATUS_ACTIVE,
    STATUS_FIELD_NAME,
    STATUS_FILE_ENV_VAR,
    STATUS_FILE_FIELD_NAME,
    STATUS_FILE_NAME,
    STATUS_FILE_TEMPORARY_SUFFIX,
    UPDATED_AT_FIELD_NAME,
    UTF8_ENCODING,
)


def resolve_status_file_path(
    explicit_path: str | None,
    base_directory: Path | None,
    run_slug: str,
) -> Path:
    """Resolve status file from CLI flag, env var, or default under base_directory.

    Args:
        explicit_path: ``--status-file`` value, or None.
        base_directory: Directory that owns the default relative path when no
            flag or env is set. When None, uses the process current directory.
        run_slug: When non-empty (and no explicit/env path), place the status
            file under ``docs/plans/<run_slug>/`` so concurrent runs do not
            share one file.

    Returns:
        Absolute path to the status file.
    """
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    environment_path = os.environ.get(STATUS_FILE_ENV_VAR)
    if environment_path:
        return Path(environment_path).expanduser().resolve()
    root_directory = base_directory if base_directory is not None else Path.cwd()
    resolved_slug = run_slug
    if resolved_slug == "":
        environment_slug = os.environ.get(RUN_SLUG_ENV_VAR)
        if environment_slug:
            resolved_slug = environment_slug
    plans_directory = root_directory.joinpath(*ALL_DEFAULT_STATUS_DIRECTORY_PARTS)
    if resolved_slug != "":
        return (plans_directory / resolved_slug / STATUS_FILE_NAME).resolve()
    return (plans_directory / STATUS_FILE_NAME).resolve()


def write_status_file(
    status_file_path: Path,
    run_status: str,
    run_slug: str,
) -> dict[str, str]:
    """Write the run status file, creating parent directories as needed.

    Args:
        status_file_path: Destination path.
        run_status: ``active`` or ``done``.
        run_slug: Run slug stored when non-empty; pass empty string to omit.

    Returns:
        The payload written to disk.

    Raises:
        ValueError: When ``run_status`` is not a valid status token.
    """
    if run_status not in ALL_VALID_RUN_STATUSES:
        raise ValueError(f"invalid status: {run_status}")
    payload: dict[str, str] = {
        STATUS_FIELD_NAME: run_status,
        UPDATED_AT_FIELD_NAME: datetime.now(timezone.utc).isoformat(),
    }
    if run_slug != "":
        payload[RUN_SLUG_FIELD_NAME] = run_slug
    status_file_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_payload = json.dumps(payload, indent=JSON_INDENT_SPACES) + "\n"
    temporary_path = status_file_path.with_name(
        status_file_path.name + STATUS_FILE_TEMPORARY_SUFFIX
    )
    temporary_path.write_text(serialized_payload, encoding=UTF8_ENCODING)
    temporary_path.replace(status_file_path)
    return payload


def decide_should_reschedule(status_file_path: Path) -> tuple[bool, str]:
    """Decide whether the orchestrator refresh loop may re-arm.

    Args:
        status_file_path: Path to the run status file.

    Returns:
        ``(is_reschedule_allowed, reason_code)``. Fail closed on missing/invalid.
    """
    if not status_file_path.is_file():
        return False, REASON_MISSING_STATUS_FILE
    try:
        loaded_payload = json.loads(status_file_path.read_text(encoding=UTF8_ENCODING))
    except (OSError, json.JSONDecodeError):
        return False, REASON_INVALID_STATUS_FILE
    if not isinstance(loaded_payload, dict):
        return False, REASON_INVALID_STATUS_FILE
    run_status = loaded_payload.get(STATUS_FIELD_NAME)
    if run_status == RUN_STATUS_ACTIVE:
        return True, REASON_ACTIVE
    return False, REASON_STATUS_NOT_ACTIVE


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build the set / should-reschedule CLI parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Orchestrator run status and reschedule gate.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser(
        COMMAND_SET,
        help="Write run status (active or done).",
    )
    set_parser.add_argument("--status-file", default=None)
    set_parser.add_argument(
        "--status",
        required=True,
        choices=sorted(ALL_VALID_RUN_STATUSES),
    )
    set_parser.add_argument("--run-slug", default=None)

    gate_parser = subparsers.add_parser(
        COMMAND_SHOULD_RESCHEDULE,
        help="Exit 0 only when status is active; otherwise exit 1.",
    )
    gate_parser.add_argument("--status-file", default=None)
    gate_parser.add_argument("--run-slug", default=None)
    return parser


def _normalized_run_slug(run_slug: str | None) -> str:
    """Return a non-None run slug string for path resolution.

    Args:
        run_slug: Optional CLI value.

    Returns:
        The slug, or empty string when unset.
    """
    if run_slug is None:
        return ""
    return run_slug


def _run_set_command(
    status_file: str | None,
    run_status: str,
    run_slug: str,
) -> int:
    """Write status JSON for the set subcommand.

    Args:
        status_file: Optional explicit status path.
        run_status: ``active`` or ``done``.
        run_slug: Run slug for path scoping and payload.

    Returns:
        Process exit code.
    """
    status_file_path = resolve_status_file_path(status_file, None, run_slug)
    payload = write_status_file(
        status_file_path=status_file_path,
        run_status=run_status,
        run_slug=run_slug,
    )
    print(json.dumps(payload, indent=JSON_INDENT_SPACES))
    return EXIT_CODE_SUCCESS


def _run_should_reschedule_command(
    status_file: str | None,
    run_slug: str,
) -> int:
    """Evaluate whether a one-shot re-arm is allowed.

    Args:
        status_file: Optional explicit status path.
        run_slug: Run slug for path scoping.

    Returns:
        Exit 0 when active; exit 1 when the loop must stop.
    """
    status_file_path = resolve_status_file_path(status_file, None, run_slug)
    is_reschedule_allowed, reason_code = decide_should_reschedule(status_file_path)
    report = {
        RESCHEDULE_FIELD_NAME: is_reschedule_allowed,
        REASON_FIELD_NAME: reason_code,
        STATUS_FILE_FIELD_NAME: str(status_file_path),
    }
    print(json.dumps(report, indent=JSON_INDENT_SPACES))
    if is_reschedule_allowed:
        return EXIT_CODE_SUCCESS
    return EXIT_CODE_STOP


def main() -> int:
    """CLI entrypoint for set and should-reschedule.

    Returns:
        Process exit code.
    """
    parsed_arguments = _build_argument_parser().parse_args()
    if parsed_arguments.command not in ALL_COMMANDS:
        return EXIT_CODE_USAGE_ERROR
    selected_run_slug = _normalized_run_slug(parsed_arguments.run_slug)
    if parsed_arguments.command == COMMAND_SET:
        return _run_set_command(
            status_file=parsed_arguments.status_file,
            run_status=parsed_arguments.status,
            run_slug=selected_run_slug,
        )
    return _run_should_reschedule_command(
        status_file=parsed_arguments.status_file,
        run_slug=selected_run_slug,
    )


if __name__ == "__main__":
    sys.exit(main())
