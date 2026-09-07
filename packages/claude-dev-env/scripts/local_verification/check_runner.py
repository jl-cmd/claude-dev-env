from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeAlias

from .check_support import (
    _prepare_check_invocation,
    _record_missing_check,
    _write_logs,
)
from .command_runner import run_command as _run_command
from .config import (
    CLI_CHECK_FINISH_MESSAGE_TEMPLATE,
    CLI_CHECK_START_MESSAGE_TEMPLATE,
    COLLECTED_TESTS_PATTERN,
    COLLECTION_ERROR_KIND,
    COLLECTION_STDERR_LOG_SUFFIX,
    COLLECTION_STDOUT_LOG_SUFFIX,
    CRASH_ERROR_KIND,
    FAILED_STATUS,
    INCOMPLETE_STATUS,
    MINIMUM_TESTS_ERROR_KIND,
    NONZERO_EXIT_ERROR_KIND,
    PASSED_STATUS,
    PYTEST_COLLECTION_FLAG,
    PYTEST_QUIET_FLAG,
    SAFE_LOG_NAME_PATTERN,
    SKIPPED_TESTS_ERROR_KIND,
    SKIPPED_TESTS_PATTERN,
    STDERR_LOG_SUFFIX,
    STDOUT_LOG_SUFFIX,
    SUCCESS_EXIT_CODE,
)
from .model import (
    CheckLogPaths,
    CheckRecord,
    CheckSpec,
    CommandCapture,
    VerificationManifest,
)

ProgressCallback: TypeAlias = Callable[[str], None]


def execute_all_checks(
    manifest: VerificationManifest,
    repository_path: Path,
    base_revision: str,
    logs_directory: Path,
    progress_callback: ProgressCallback | None,
) -> tuple[CheckRecord, ...]:
    """Execute every check in the manifest.

    Args:
        manifest: Checks to execute.

    Returns:
        One record for each check.
    """
    return tuple(
        _execute_check(
            each_check,
            repository_path,
            base_revision,
            logs_directory,
            progress_callback,
        )
        for each_check in manifest.checks
    )


def _execute_check(
    check: CheckSpec,
    repository_path: Path,
    base_revision: str,
    logs_directory: Path,
    progress_callback: ProgressCallback | None,
) -> CheckRecord:
    _emit_progress(
        progress_callback,
        CLI_CHECK_START_MESSAGE_TEMPLATE.format(check_id=check.check_id),
    )
    check_log_paths = _build_check_log_paths(check, logs_directory)
    check_directory, all_arguments = _prepare_check_invocation(
        check, repository_path, base_revision
    )
    if not check_directory.is_dir():
        check_record = _record_missing_check(
            check, all_arguments, check_directory, check_log_paths
        )
        return _finish_with_progress(progress_callback, check, check_record)
    check_record = _run_existing_check(
        check, all_arguments, check_directory, check_log_paths
    )
    return _finish_with_progress(progress_callback, check, check_record)


def _build_check_log_paths(check: CheckSpec, logs_directory: Path) -> CheckLogPaths:
    safe_check_id = SAFE_LOG_NAME_PATTERN.sub("_", check.check_id)
    return CheckLogPaths(
        logs_directory / (safe_check_id + STDOUT_LOG_SUFFIX),
        logs_directory / (safe_check_id + STDERR_LOG_SUFFIX),
        logs_directory / (safe_check_id + COLLECTION_STDOUT_LOG_SUFFIX),
        logs_directory / (safe_check_id + COLLECTION_STDERR_LOG_SUFFIX),
    )


def _run_existing_check(
    check: CheckSpec,
    all_arguments: tuple[str, ...],
    check_directory: Path,
    check_log_paths: CheckLogPaths,
) -> CheckRecord:
    all_collection_capture = _collect_minimum_tests(
        check,
        all_arguments,
        check_directory,
        check_log_paths.collection_stdout,
        check_log_paths.collection_stderr,
    )
    started_at = time.monotonic()
    command_capture = _run_command(
        all_arguments, check_directory, check.timeout_seconds
    )
    duration_seconds = time.monotonic() - started_at
    return _finish_check(
        check,
        all_arguments,
        check_directory,
        check_log_paths,
        all_collection_capture,
        command_capture,
        duration_seconds,
    )


def _finish_with_progress(
    progress_callback: ProgressCallback | None,
    check: CheckSpec,
    check_record: CheckRecord,
) -> CheckRecord:
    _emit_progress(
        progress_callback,
        CLI_CHECK_FINISH_MESSAGE_TEMPLATE.format(
            check_id=check.check_id, status=check_record.status
        ),
    )
    return check_record


def _emit_progress(
    progress_callback: ProgressCallback | None, progress_message: str
) -> None:
    if progress_callback is not None:
        progress_callback(progress_message)


def _finish_check(
    check: CheckSpec,
    all_arguments: tuple[str, ...],
    check_directory: Path,
    check_log_paths: CheckLogPaths,
    all_collection_capture: tuple[CommandCapture, int | None] | None,
    command_capture: CommandCapture,
    duration_seconds: float,
) -> CheckRecord:
    _write_logs(
        check_log_paths.stdout,
        check_log_paths.stderr,
        command_capture.stdout_text,
        command_capture.stderr_text,
    )
    return _build_finished_record(
        check,
        all_arguments,
        check_directory,
        check_log_paths,
        all_collection_capture,
        command_capture,
        duration_seconds,
    )


def _build_finished_record(
    check: CheckSpec,
    all_arguments: tuple[str, ...],
    check_directory: Path,
    check_log_paths: CheckLogPaths,
    all_collection_capture: tuple[CommandCapture, int | None] | None,
    command_capture: CommandCapture,
    duration_seconds: float,
) -> CheckRecord:
    status, error_kind, error_message = _classify_record(
        check, all_collection_capture, command_capture
    )
    return CheckRecord(
        check.check_id,
        status,
        all_arguments,
        str(check_directory),
        command_capture.exit_code,
        duration_seconds,
        check_log_paths.stdout,
        check_log_paths.stderr,
        error_kind,
        error_message,
        check.minimum_tests,
        all_collection_capture[1] if all_collection_capture is not None else None,
        all_collection_capture[0].exit_code
        if all_collection_capture is not None
        else None,
    )


def _classify_record(
    check: CheckSpec,
    all_collection_capture: tuple[CommandCapture, int | None] | None,
    command_capture: CommandCapture,
) -> tuple[str, str | None, str | None]:
    status, error_kind, error_message = _classify_command(command_capture)
    if all_collection_capture is None:
        return status, error_kind, error_message
    status, error_kind, error_message = _classify_collection(
        check, all_collection_capture, status, error_kind, error_message
    )
    return _classify_skipped_tests(
        check,
        all_collection_capture,
        command_capture,
        status,
        error_kind,
        error_message,
    )


def _collect_minimum_tests(
    check: CheckSpec,
    all_arguments: tuple[str, ...],
    check_directory: Path,
    stdout_log_path: Path,
    stderr_log_path: Path,
) -> tuple[CommandCapture, int | None] | None:
    if check.minimum_tests is None:
        return None
    collection_arguments = _collection_arguments(all_arguments)
    collection_capture = _run_command(
        collection_arguments, check_directory, check.timeout_seconds
    )
    _write_logs(
        stdout_log_path,
        stderr_log_path,
        collection_capture.stdout_text,
        collection_capture.stderr_text,
    )
    collected_tests = _parse_collected_tests(collection_capture)
    return collection_capture, collected_tests


def _collection_arguments(all_arguments: tuple[str, ...]) -> tuple[str, ...]:
    all_collection_arguments = list(all_arguments)
    if PYTEST_COLLECTION_FLAG not in all_collection_arguments:
        all_collection_arguments.append(PYTEST_COLLECTION_FLAG)
    if PYTEST_QUIET_FLAG not in all_collection_arguments:
        all_collection_arguments.append(PYTEST_QUIET_FLAG)
    return tuple(all_collection_arguments)


def _parse_collected_tests(command_capture: CommandCapture) -> int | None:
    all_text = command_capture.stdout_text + command_capture.stderr_text
    test_match = COLLECTED_TESTS_PATTERN.search(all_text)
    if test_match is None:
        return 0 if command_capture.exit_code == 5 else None
    return int(test_match.group("count"))


def _parse_skipped_tests(command_capture: CommandCapture) -> int:
    all_text = command_capture.stdout_text + command_capture.stderr_text
    skipped_match = SKIPPED_TESTS_PATTERN.search(all_text)
    if skipped_match is None:
        return 0
    return int(skipped_match.group("count"))


def _classify_skipped_tests(
    check: CheckSpec,
    all_collection_capture: tuple[CommandCapture, int | None],
    command_capture: CommandCapture,
    status: str,
    error_kind: str | None,
    error_message: str | None,
) -> tuple[str, str | None, str | None]:
    if status != PASSED_STATUS:
        return status, error_kind, error_message
    if not _has_skipped_required_tests(check, all_collection_capture, command_capture):
        return status, error_kind, error_message
    return INCOMPLETE_STATUS, SKIPPED_TESTS_ERROR_KIND, "Required tests were skipped"


def _has_skipped_required_tests(
    check: CheckSpec,
    all_collection_capture: tuple[CommandCapture, int | None],
    command_capture: CommandCapture,
) -> bool:
    if check.minimum_tests is None:
        return False
    collection_capture, collected_tests = all_collection_capture
    if collection_capture.exit_code != SUCCESS_EXIT_CODE:
        return False
    if collected_tests is None or collected_tests == 0:
        return False
    return _parse_skipped_tests(command_capture) > 0


def _classify_collection(
    check: CheckSpec,
    all_collection_capture: tuple[CommandCapture, int | None],
    status: str,
    error_kind: str | None,
    error_message: str | None,
) -> tuple[str, str | None, str | None]:
    command_capture, collected_tests = all_collection_capture
    if (
        check.minimum_tests is not None
        and collected_tests is not None
        and collected_tests < check.minimum_tests
    ):
        return FAILED_STATUS, MINIMUM_TESTS_ERROR_KIND, "Minimum test count was not met"
    if status == FAILED_STATUS:
        return status, error_kind, error_message
    if command_capture.error_kind is not None:
        return INCOMPLETE_STATUS, COLLECTION_ERROR_KIND, command_capture.error_message
    if command_capture.exit_code != SUCCESS_EXIT_CODE:
        return INCOMPLETE_STATUS, COLLECTION_ERROR_KIND, "Pytest collection failed"
    if collected_tests is None:
        return (
            INCOMPLETE_STATUS,
            COLLECTION_ERROR_KIND,
            "Pytest collection count is missing",
        )
    return status, error_kind, error_message


def _classify_command(
    command_capture: CommandCapture,
) -> tuple[str, str | None, str | None]:
    if command_capture.error_kind is not None:
        return (
            INCOMPLETE_STATUS,
            command_capture.error_kind,
            command_capture.error_message,
        )
    if command_capture.exit_code is None:
        return INCOMPLETE_STATUS, CRASH_ERROR_KIND, "Command ended without an exit code"
    if command_capture.exit_code < 0:
        return INCOMPLETE_STATUS, CRASH_ERROR_KIND, "Command ended from a signal"
    if command_capture.exit_code != SUCCESS_EXIT_CODE:
        return (
            FAILED_STATUS,
            NONZERO_EXIT_ERROR_KIND,
            "Command returned a nonzero exit code",
        )
    return PASSED_STATUS, None, None
