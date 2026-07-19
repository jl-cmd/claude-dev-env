#!/usr/bin/env python3
"""Deterministic orchestrator status gate: status JSON and reschedule exit codes.

::

    python status_gate.py set --status active|done
    python status_gate.py begin-firing
    python status_gate.py should-reschedule
    python status_gate.py claim-rearm
    python status_gate.py release-rearm

``should-reschedule`` and ``claim-rearm`` exit 0 only when status is
``active`` and no re-arm slot is already pending. ``claim-rearm`` also
sets the pending latch. ``begin-firing`` clears the latch at the start
of a refresh firing. Missing or invalid status files fail closed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from status_gate_constants.config.constants import (
    ALL_COMMANDS,
    ALL_DEFAULT_STATUS_DIRECTORY_PARTS,
    ALL_VALID_RUN_STATUSES,
    COMMAND_BEGIN_FIRING,
    COMMAND_CLAIM_REARM,
    COMMAND_RELEASE_REARM,
    COMMAND_SET,
    COMMAND_SHOULD_RESCHEDULE,
    EXIT_CODE_STOP,
    EXIT_CODE_SUCCESS,
    EXIT_CODE_USAGE_ERROR,
    JSON_INDENT_SPACES,
    REARM_PENDING_FIELD_NAME,
    REASON_ACTIVE,
    REASON_FIELD_NAME,
    REASON_FIRING_STARTED,
    REASON_INVALID_STATUS_FILE,
    REASON_MISSING_STATUS_FILE,
    REASON_REARM_ALREADY_PENDING,
    REASON_REARM_SLOT_CLAIMED,
    REASON_REARM_SLOT_RELEASED,
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


class StatusFilePayload(TypedDict, total=False):
    """On-disk orchestrator run status JSON shape."""

    status: str
    updated_at: str
    rearm_pending: bool
    run_slug: str


RearmMutation = Callable[[Path, str], tuple[bool, str, StatusFilePayload | None]]


def _encode_status_file_payload(
    run_status: str,
    run_slug: str,
    is_rearm_pending: bool,
) -> StatusFilePayload:
    """Build a status payload for disk write.

    Args:
        run_status: ``active`` or ``done``.
        run_slug: Run slug stored when non-empty; pass empty string to omit.
        is_rearm_pending: Whether a one-shot re-arm is already reserved.

    Returns:
        Typed status payload ready for serialization.
    """
    all_status_fields: StatusFilePayload = {
        STATUS_FIELD_NAME: run_status,
        UPDATED_AT_FIELD_NAME: datetime.now(timezone.utc).isoformat(),
        REARM_PENDING_FIELD_NAME: is_rearm_pending,
    }
    if run_slug != "":
        all_status_fields[RUN_SLUG_FIELD_NAME] = run_slug
    return all_status_fields


def _decode_status_file_payload(
    all_loaded_fields: dict[object, object],
) -> StatusFilePayload | None:
    """Parse a raw JSON object into StatusFilePayload, or None if invalid.

    Args:
        all_loaded_fields: Decoded JSON object.

    Returns:
        Typed status payload, or None when the shape is wrong.
    """
    all_status_fields: StatusFilePayload = {}
    for each_field_name, each_field_entry in all_loaded_fields.items():
        if not isinstance(each_field_name, str):
            return None
        if each_field_name == STATUS_FIELD_NAME:
            if not isinstance(each_field_entry, str):
                return None
            all_status_fields[STATUS_FIELD_NAME] = each_field_entry
            continue
        if each_field_name == UPDATED_AT_FIELD_NAME:
            if not isinstance(each_field_entry, str):
                return None
            all_status_fields[UPDATED_AT_FIELD_NAME] = each_field_entry
            continue
        if each_field_name == RUN_SLUG_FIELD_NAME:
            if not isinstance(each_field_entry, str):
                return None
            all_status_fields[RUN_SLUG_FIELD_NAME] = each_field_entry
            continue
        if each_field_name == REARM_PENDING_FIELD_NAME:
            if not isinstance(each_field_entry, bool):
                return None
            all_status_fields[REARM_PENDING_FIELD_NAME] = each_field_entry
            continue
        return None
    return all_status_fields


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
    is_rearm_pending: bool,
) -> StatusFilePayload:
    """Write the run status file, creating parent directories as needed.

    Args:
        status_file_path: Destination path.
        run_status: ``active`` or ``done``.
        run_slug: Run slug stored when non-empty; pass empty string to omit.
        is_rearm_pending: Whether a one-shot re-arm is already reserved.

    Returns:
        The payload written to disk.

    Raises:
        ValueError: When ``run_status`` is not a valid status token.
    """
    if run_status not in ALL_VALID_RUN_STATUSES:
        raise ValueError(f"invalid status: {run_status}")
    all_status_fields = _encode_status_file_payload(
        run_status=run_status,
        run_slug=run_slug,
        is_rearm_pending=is_rearm_pending,
    )
    return _atomic_write_payload(status_file_path, all_status_fields)


def _atomic_write_payload(
    status_file_path: Path,
    all_status_fields: StatusFilePayload,
) -> StatusFilePayload:
    """Write a status payload atomically.

    Args:
        status_file_path: Destination path.
        all_status_fields: JSON-serializable status mapping.

    Returns:
        The same payload.
    """
    status_file_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_payload = json.dumps(all_status_fields, indent=JSON_INDENT_SPACES) + "\n"
    temporary_path = status_file_path.with_name(
        status_file_path.name + STATUS_FILE_TEMPORARY_SUFFIX
    )
    temporary_path.write_text(serialized_payload, encoding=UTF8_ENCODING)
    temporary_path.replace(status_file_path)
    return all_status_fields


def _load_status_payload(
    status_file_path: Path,
) -> tuple[StatusFilePayload | None, str | None]:
    """Load and validate the status file payload.

    Args:
        status_file_path: Path to the run status file.

    Returns:
        ``(payload, None)`` on success, or ``(None, reason_code)`` on failure.
    """
    if not status_file_path.is_file():
        return None, REASON_MISSING_STATUS_FILE
    try:
        loaded_payload = json.loads(status_file_path.read_text(encoding=UTF8_ENCODING))
    except (OSError, json.JSONDecodeError):
        return None, REASON_INVALID_STATUS_FILE
    if not isinstance(loaded_payload, dict):
        return None, REASON_INVALID_STATUS_FILE
    all_status_fields = _decode_status_file_payload(loaded_payload)
    if all_status_fields is None:
        return None, REASON_INVALID_STATUS_FILE
    return all_status_fields, None


def _is_rearm_pending(all_status_fields: StatusFilePayload) -> bool:
    """Return whether the payload marks a re-arm slot as pending.

    Args:
        all_status_fields: Loaded status mapping.

    Returns:
        True when ``rearm_pending`` is truthy.
    """
    return bool(all_status_fields.get(REARM_PENDING_FIELD_NAME, False))


def _status_file_run_slug(
    all_status_fields: StatusFilePayload,
    fallback_run_slug: str,
) -> str:
    """Prefer the slug stored in the payload when present.

    Args:
        all_status_fields: Loaded status mapping.
        fallback_run_slug: CLI or empty slug.

    Returns:
        Slug string for rewrites.
    """
    stored_slug = all_status_fields.get(RUN_SLUG_FIELD_NAME)
    if isinstance(stored_slug, str) and stored_slug != "":
        return stored_slug
    return fallback_run_slug


def _load_active_status(
    status_file_path: Path,
) -> tuple[StatusFilePayload | None, str | None]:
    """Load the status payload and require an active run.

    Args:
        status_file_path: Path to the run status file.

    Returns:
        ``(payload, None)`` when the file loads and status is ``active``;
        ``(None, reason_code)`` on a missing/invalid file or inactive status.
    """
    all_status_fields, load_failure_reason = _load_status_payload(status_file_path)
    if all_status_fields is None:
        return None, load_failure_reason
    if all_status_fields.get(STATUS_FIELD_NAME) != RUN_STATUS_ACTIVE:
        return None, REASON_STATUS_NOT_ACTIVE
    return all_status_fields, None


def decide_should_reschedule(status_file_path: Path) -> tuple[bool, str]:
    """Decide whether the orchestrator refresh loop may re-arm.

    Args:
        status_file_path: Path to the run status file.

    Returns:
        ``(is_reschedule_allowed, reason_code)``. Fail closed on missing/invalid
        status, inactive status, or an already-pending re-arm slot.
    """
    all_status_fields, load_failure_reason = _load_active_status(status_file_path)
    if all_status_fields is None:
        assert load_failure_reason is not None
        return False, load_failure_reason
    if _is_rearm_pending(all_status_fields):
        return False, REASON_REARM_ALREADY_PENDING
    return True, REASON_ACTIVE


def _apply_rearm_latch(
    status_file_path: Path,
    run_slug: str,
    is_rearm_pending: bool,
    success_reason: str,
) -> tuple[bool, str, StatusFilePayload | None]:
    """Rewrite the re-arm latch of an active run and report the outcome.

    Setting the latch (``is_rearm_pending`` True) is a claim: it fails with
    ``REASON_REARM_ALREADY_PENDING`` when a slot is already reserved. Clearing
    the latch (False) always succeeds while the run is active.

    Args:
        status_file_path: Path to the run status file.
        run_slug: Fallback slug when the file has none.
        is_rearm_pending: Latch value to write.
        success_reason: Reason code returned when the rewrite lands.

    Returns:
        ``(is_applied, reason_code, payload_or_none)``.
    """
    all_status_fields, load_failure_reason = _load_active_status(status_file_path)
    if all_status_fields is None:
        assert load_failure_reason is not None
        return False, load_failure_reason, None
    if is_rearm_pending and _is_rearm_pending(all_status_fields):
        return False, REASON_REARM_ALREADY_PENDING, None
    written_status = write_status_file(
        status_file_path=status_file_path,
        run_status=RUN_STATUS_ACTIVE,
        run_slug=_status_file_run_slug(all_status_fields, run_slug),
        is_rearm_pending=is_rearm_pending,
    )
    return True, success_reason, written_status


def begin_firing(
    status_file_path: Path,
    run_slug: str,
) -> tuple[bool, str, StatusFilePayload | None]:
    """Clear the re-arm latch at the start of a refresh firing.

    Args:
        status_file_path: Path to the run status file.
        run_slug: Fallback slug when the file has none.

    Returns:
        ``(is_allowed, reason_code, payload_or_none)``.
    """
    return _apply_rearm_latch(
        status_file_path,
        run_slug,
        is_rearm_pending=False,
        success_reason=REASON_FIRING_STARTED,
    )


def claim_rearm_slot(
    status_file_path: Path,
    run_slug: str,
) -> tuple[bool, str, StatusFilePayload | None]:
    """Atomically reserve the single re-arm slot when active and free.

    Args:
        status_file_path: Path to the run status file.
        run_slug: Fallback slug when the file has none.

    Returns:
        ``(is_claimed, reason_code, payload_or_none)``.
    """
    return _apply_rearm_latch(
        status_file_path,
        run_slug,
        is_rearm_pending=True,
        success_reason=REASON_REARM_SLOT_CLAIMED,
    )


def release_rearm_slot(
    status_file_path: Path,
    run_slug: str,
) -> tuple[bool, str, StatusFilePayload | None]:
    """Clear a reserved re-arm slot after a failed host schedule create.

    Args:
        status_file_path: Path to the run status file.
        run_slug: Fallback slug when the file has none.

    Returns:
        ``(is_released, reason_code, payload_or_none)``.
    """
    return _apply_rearm_latch(
        status_file_path,
        run_slug,
        is_rearm_pending=False,
        success_reason=REASON_REARM_SLOT_RELEASED,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build the status-gate CLI parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Orchestrator run status and single-pending re-arm gate.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser(
        COMMAND_SET,
        help="Write run status (active or done); clears rearm_pending.",
    )
    set_parser.add_argument("--status-file", default=None)
    set_parser.add_argument(
        "--status",
        required=True,
        choices=sorted(ALL_VALID_RUN_STATUSES),
    )
    set_parser.add_argument("--run-slug", default=None)

    for each_command, each_help in (
        (
            COMMAND_SHOULD_RESCHEDULE,
            "Exit 0 when active and rearm_pending is false (read-only).",
        ),
        (
            COMMAND_BEGIN_FIRING,
            "Clear rearm_pending at refresh start; exit 0 when active.",
        ),
        (
            COMMAND_CLAIM_REARM,
            "Reserve the re-arm slot (active and not pending); exit 0 on claim.",
        ),
        (
            COMMAND_RELEASE_REARM,
            "Clear rearm_pending after a failed host schedule create.",
        ),
    ):
        each_parser = subparsers.add_parser(each_command, help=each_help)
        each_parser.add_argument("--status-file", default=None)
        each_parser.add_argument("--run-slug", default=None)
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


def _print_gate_report(
    is_reschedule_allowed: bool,
    reason_code: str,
    status_file_path: Path,
) -> None:
    """Print the standard JSON gate report to stdout.

    Args:
        is_reschedule_allowed: Whether the caller may proceed.
        reason_code: Machine reason string.
        status_file_path: Resolved status path.
    """
    report = {
        RESCHEDULE_FIELD_NAME: is_reschedule_allowed,
        REASON_FIELD_NAME: reason_code,
        STATUS_FILE_FIELD_NAME: str(status_file_path),
    }
    print(json.dumps(report, indent=JSON_INDENT_SPACES))


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
    written_status = write_status_file(
        status_file_path=status_file_path,
        run_status=run_status,
        run_slug=run_slug,
        is_rearm_pending=False,
    )
    print(json.dumps(written_status, indent=JSON_INDENT_SPACES))
    return EXIT_CODE_SUCCESS


def _report_and_exit(
    is_allowed: bool,
    reason_code: str,
    status_file_path: Path,
) -> int:
    """Print the JSON gate report and map the decision to an exit code.

    Args:
        is_allowed: Whether the caller may proceed.
        reason_code: Machine reason string.
        status_file_path: Resolved status path.

    Returns:
        ``EXIT_CODE_SUCCESS`` when allowed, else ``EXIT_CODE_STOP``.
    """
    _print_gate_report(is_allowed, reason_code, status_file_path)
    if is_allowed:
        return EXIT_CODE_SUCCESS
    return EXIT_CODE_STOP


def _run_should_reschedule_command(
    status_file: str | None,
    run_slug: str,
) -> int:
    """Evaluate whether a one-shot re-arm is allowed (read-only).

    Args:
        status_file: Optional explicit status path.
        run_slug: Run slug for path scoping.

    Returns:
        Exit 0 when active and free; exit 1 when the loop must not re-arm.
    """
    status_file_path = resolve_status_file_path(status_file, None, run_slug)
    is_reschedule_allowed, reason_code = decide_should_reschedule(status_file_path)
    return _report_and_exit(is_reschedule_allowed, reason_code, status_file_path)


def _run_rearm_mutation_command(
    mutation: RearmMutation,
    status_file: str | None,
    run_slug: str,
) -> int:
    """Run a re-arm latch mutation and map its decision to an exit code.

    Args:
        mutation: begin_firing, claim_rearm_slot, or release_rearm_slot.
        status_file: Optional explicit status path.
        run_slug: Run slug for path scoping.

    Returns:
        Exit 0 when the mutation lands; exit 1 otherwise.
    """
    status_file_path = resolve_status_file_path(status_file, None, run_slug)
    is_applied, reason_code, _payload = mutation(status_file_path, run_slug)
    return _report_and_exit(is_applied, reason_code, status_file_path)


def main() -> int:
    """CLI entrypoint for status and re-arm latch commands.

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
    if parsed_arguments.command == COMMAND_SHOULD_RESCHEDULE:
        return _run_should_reschedule_command(
            status_file=parsed_arguments.status_file,
            run_slug=selected_run_slug,
        )
    rearm_mutations: dict[str, RearmMutation] = {
        COMMAND_BEGIN_FIRING: begin_firing,
        COMMAND_CLAIM_REARM: claim_rearm_slot,
        COMMAND_RELEASE_REARM: release_rearm_slot,
    }
    selected_mutation = rearm_mutations.get(parsed_arguments.command)
    if selected_mutation is not None:
        return _run_rearm_mutation_command(
            selected_mutation,
            status_file=parsed_arguments.status_file,
            run_slug=selected_run_slug,
        )
    return EXIT_CODE_USAGE_ERROR


if __name__ == "__main__":
    sys.exit(main())
