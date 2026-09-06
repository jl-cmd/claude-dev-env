from __future__ import annotations

import sys
from pathlib import Path

from .config import (
    BASE_PLACEHOLDER,
    CDE_LINT_PLACEHOLDER,
    INCOMPLETE_STATUS,
    PYTHON_PLACEHOLDER,
    REPOSITORY_PLACEHOLDER,
    REPOSITORY_POLICY_PLACEHOLDER,
    START_ERROR_KIND,
    UTF8_ENCODING,
)
from .model import CheckLogPaths, CheckRecord, CheckSpec


def _prepare_check_invocation(
    check: CheckSpec, repository_path: Path, base_revision: str
) -> tuple[Path, tuple[str, ...]]:
    check_directory = repository_path / check.cwd
    all_arguments = _substitute_arguments(
        check.command_arguments, repository_path, base_revision
    )
    return check_directory, all_arguments


def _record_missing_check(
    check: CheckSpec,
    all_arguments: tuple[str, ...],
    check_directory: Path,
    check_log_paths: CheckLogPaths,
) -> CheckRecord:
    _write_logs(
        check_log_paths.stdout, check_log_paths.stderr, "", "Missing check directory"
    )
    return _incomplete_record(
        check,
        all_arguments,
        check_directory,
        check_log_paths.stdout,
        check_log_paths.stderr,
        START_ERROR_KIND,
        "Check cwd does not exist",
    )


def _substitute_arguments(
    all_arguments: tuple[str, ...], repository_path: Path, base_revision: str
) -> tuple[str, ...]:
    package_root = Path(__file__).resolve().parents[2]
    replacement_by_placeholder = {
        PYTHON_PLACEHOLDER: sys.executable,
        REPOSITORY_PLACEHOLDER: str(repository_path),
        BASE_PLACEHOLDER: base_revision,
        CDE_LINT_PLACEHOLDER: str(package_root / "scripts" / "cde_lint.py"),
        REPOSITORY_POLICY_PLACEHOLDER: str(
            package_root / "scripts" / "repository_policy.py"
        ),
    }
    return tuple(
        replacement_by_placeholder.get(each_argument, each_argument)
        for each_argument in all_arguments
    )


def _write_logs(
    stdout_log_path: Path,
    stderr_log_path: Path,
    stdout_text: str,
    stderr_text: str,
) -> None:
    stdout_log_path.write_text(stdout_text, encoding=UTF8_ENCODING)
    stderr_log_path.write_text(stderr_text, encoding=UTF8_ENCODING)


def _incomplete_record(
    check: CheckSpec,
    all_arguments: tuple[str, ...],
    check_directory: Path,
    stdout_log_path: Path,
    stderr_log_path: Path,
    error_kind: str,
    error_message: str,
) -> CheckRecord:
    return CheckRecord(
        check.check_id,
        INCOMPLETE_STATUS,
        all_arguments,
        str(check_directory),
        None,
        0.0,
        stdout_log_path,
        stderr_log_path,
        error_kind,
        error_message,
        check.minimum_tests,
    )
