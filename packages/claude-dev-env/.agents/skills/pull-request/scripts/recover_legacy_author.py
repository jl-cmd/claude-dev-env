"""Restore one explicitly selected legacy GitHub author-swap record."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from github_pr_command_constants.config.constants import (
    ALL_GH_AUTH_SWITCH_COMMAND_HEAD,
    LEGACY_RECORD_ACTIVE_MESSAGE,
    LEGACY_RECORD_CHANGED_MESSAGE,
    LEGACY_RECORD_CONFIRMATION_MESSAGE,
    LEGACY_RECORD_INACTIVE_CONFIRMATION_FLAG,
    LEGACY_RECORD_NAME_PATTERN,
    LEGACY_RECORD_ORIGINAL_ACCOUNT_KEY,
    LEGACY_RECORD_PERMISSION_MODE,
    LEGACY_RECORD_REJECTED_MESSAGE,
    LEGACY_RECORD_STALE_AGE_SECONDS,
    LEGACY_RESTORE_FAILED_MESSAGE,
    RECOVERY_CLEAN_EXIT_CODE,
    RECOVERY_FAILED_EXIT_CODE,
    RECOVERY_REJECTED_EXIT_CODE,
    RECOVERY_UNRESOLVED_EXIT_CODE,
)

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
FileFingerprint = tuple[int, int, int, int, int]
VerifiedRecord = tuple[str, FileFingerprint]


class LegacyRecordRejected(ValueError):
    """Report an invalid legacy state record."""


class LegacyRecordActive(ValueError):
    """Report a legacy state record that is not old enough for recovery."""


class LegacyRecordChanged(ValueError):
    """Report a legacy state record that changed during recovery."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("state_file", type=Path)
    parser.add_argument(LEGACY_RECORD_INACTIVE_CONFIRMATION_FLAG, action="store_true")
    return parser


def _posix_metadata_is_secure(
    file_mode: int,
    file_owner_id: int,
    current_user_id: int | None,
) -> bool:
    if not stat.S_ISREG(file_mode):
        return False
    if current_user_id is None:
        return True
    return (
        stat.S_IMODE(file_mode) == LEGACY_RECORD_PERMISSION_MODE
        and file_owner_id == current_user_id
    )


def _secure_metadata(
    state_file: Path,
    current_user_id: int | None,
) -> os.stat_result:
    try:
        file_metadata = state_file.lstat()
    except OSError as error:
        raise LegacyRecordRejected from error
    if not _posix_metadata_is_secure(
        file_metadata.st_mode,
        file_metadata.st_uid,
        current_user_id,
    ):
        raise LegacyRecordRejected
    return file_metadata


def _fingerprint(file_metadata: os.stat_result) -> FileFingerprint:
    return (
        file_metadata.st_dev,
        file_metadata.st_ino,
        file_metadata.st_mode,
        file_metadata.st_size,
        file_metadata.st_mtime_ns,
    )


def _parse_original_account(record_text: str) -> str:
    try:
        decoded_record = json.loads(record_text)
    except json.JSONDecodeError as error:
        raise LegacyRecordRejected from error
    if not isinstance(decoded_record, dict):
        raise LegacyRecordRejected
    if set(decoded_record) != {LEGACY_RECORD_ORIGINAL_ACCOUNT_KEY}:
        raise LegacyRecordRejected
    original_account = decoded_record[LEGACY_RECORD_ORIGINAL_ACCOUNT_KEY]
    if not isinstance(original_account, str) or not original_account.strip():
        raise LegacyRecordRejected
    return original_account.strip()


def _read_verified_record(
    state_file: Path,
    now_seconds: float,
    current_user_id: int | None,
) -> VerifiedRecord:
    if LEGACY_RECORD_NAME_PATTERN.fullmatch(state_file.name) is None:
        raise LegacyRecordRejected
    initial_metadata = _secure_metadata(state_file, current_user_id)
    if now_seconds - initial_metadata.st_mtime < LEGACY_RECORD_STALE_AGE_SECONDS:
        raise LegacyRecordActive
    try:
        record_text = state_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise LegacyRecordRejected from error
    original_account = _parse_original_account(record_text)
    initial_fingerprint = _fingerprint(initial_metadata)
    verified_metadata = _secure_metadata(state_file, current_user_id)
    if _fingerprint(verified_metadata) != initial_fingerprint:
        raise LegacyRecordChanged
    return original_account, initial_fingerprint


def _delete_unchanged_record(
    state_file: Path,
    expected_fingerprint: FileFingerprint,
    current_user_id: int | None,
) -> None:
    current_metadata = _secure_metadata(state_file, current_user_id)
    if _fingerprint(current_metadata) != expected_fingerprint:
        raise LegacyRecordChanged
    try:
        state_file.unlink()
    except OSError as error:
        raise LegacyRecordChanged from error


def _load_record_with_diagnostics(
    state_file: Path,
    now_seconds: float,
    current_user_id: int | None,
) -> tuple[VerifiedRecord | None, int]:
    try:
        return _read_verified_record(state_file, now_seconds, current_user_id), 0
    except LegacyRecordActive:
        sys.stderr.write(LEGACY_RECORD_ACTIVE_MESSAGE)
        return None, RECOVERY_REJECTED_EXIT_CODE
    except LegacyRecordChanged:
        sys.stderr.write(LEGACY_RECORD_CHANGED_MESSAGE)
        return None, RECOVERY_FAILED_EXIT_CODE
    except LegacyRecordRejected:
        sys.stderr.write(LEGACY_RECORD_REJECTED_MESSAGE)
        return None, RECOVERY_REJECTED_EXIT_CODE


def _restore_and_delete(
    state_file: Path,
    verified_record: VerifiedRecord,
    current_user_id: int | None,
    command_runner: CommandRunner,
) -> int:
    original_account, expected_fingerprint = verified_record
    try:
        completed_restore = command_runner(
            [*ALL_GH_AUTH_SWITCH_COMMAND_HEAD, original_account],
            capture_output=True,
            check=False,
            shell=False,
            text=True,
        )
    except OSError:
        sys.stderr.write(LEGACY_RESTORE_FAILED_MESSAGE)
        return RECOVERY_FAILED_EXIT_CODE
    if completed_restore.returncode != 0:
        sys.stderr.write(LEGACY_RESTORE_FAILED_MESSAGE)
        return RECOVERY_FAILED_EXIT_CODE
    try:
        _delete_unchanged_record(state_file, expected_fingerprint, current_user_id)
    except (LegacyRecordChanged, LegacyRecordRejected):
        sys.stderr.write(LEGACY_RECORD_CHANGED_MESSAGE)
        return RECOVERY_FAILED_EXIT_CODE
    return RECOVERY_CLEAN_EXIT_CODE


def _recover_selected_record(
    state_file: Path,
    now_seconds: float,
    current_user_id: int | None,
    command_runner: CommandRunner,
) -> int:
    verified_record, exit_code = _load_record_with_diagnostics(
        state_file, now_seconds, current_user_id
    )
    if verified_record is None:
        return exit_code
    return _restore_and_delete(
        state_file, verified_record, current_user_id, command_runner
    )


def main(
    all_arguments: Sequence[str],
    *,
    now_seconds: float,
    current_user_id: int | None,
    command_runner: CommandRunner,
) -> int:
    """Recover one confirmed-inactive legacy state record.

    Args:
        all_arguments: Command arguments after the script name.
        now_seconds: Current wall-clock time in seconds.
        current_user_id: Current POSIX user identifier, or None on Windows.
        command_runner: Process runner used by tests and production.

    Returns:
        Zero on success, one on failure, two on rejection, or three when unresolved.
    """
    arguments = _build_parser().parse_args(list(all_arguments))
    if not arguments.confirm_inactive:
        sys.stderr.write(LEGACY_RECORD_CONFIRMATION_MESSAGE)
        return RECOVERY_UNRESOLVED_EXIT_CODE
    return _recover_selected_record(
        arguments.state_file,
        now_seconds,
        current_user_id,
        command_runner,
    )


if __name__ == "__main__":
    raise SystemExit(
        main(
            sys.argv[1:],
            now_seconds=time.time(),
            current_user_id=os.getuid() if hasattr(os, "getuid") else None,
            command_runner=subprocess.run,
        )
    )
