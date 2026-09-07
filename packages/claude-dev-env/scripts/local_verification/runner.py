from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TypeAlias

from .check_runner import _execute_check
from .config import (
    JSON_INDENT_SPACES,
    LOGS_DIRECTORY_SUFFIX,
    PASSED_STATUS,
    REPORT_NEWLINE,
    RUN_CHECK_LOG_TEMPLATE,
    RUN_LOG_FILENAME,
    UTF8_ENCODING,
)
from .git_state import CandidateSnapshot, capture_candidate_snapshot
from .manifest import compute_manifest_digest
from .model import (
    CheckRecord,
    VerificationManifest,
    VerificationReport,
)

ProgressCallback: TypeAlias = Callable[[str], None]


def run_verification(
    manifest: VerificationManifest,
    repository_path: Path,
    base_revision: str,
    report_path: Path,
    progress_callback: ProgressCallback | None = None,
) -> VerificationReport:
    """Execute checks and write the verification report.

    Args:
        manifest: Verification manifest.
        repository_path: Repository checkout to verify.
        base_revision: Base revision for selection and Git identity.
        report_path: Output path for the verification report.
        progress_callback: Optional receiver for progress lines.

    Returns:
        The written verification report.
    """
    resolved_repository_path = _require_repository_directory(repository_path)
    logs_directory = _prepare_logs_directory(report_path)
    verification_report = _verify_resolved_repository(
        manifest,
        resolved_repository_path,
        base_revision,
        logs_directory,
        progress_callback,
    )
    _write_report_files(verification_report, logs_directory, report_path)
    return verification_report


def _verify_resolved_repository(
    manifest: VerificationManifest,
    resolved_repository_path: Path,
    base_revision: str,
    logs_directory: Path,
    progress_callback: ProgressCallback | None,
) -> VerificationReport:
    before_snapshot = capture_candidate_snapshot(
        resolved_repository_path, base_revision
    )
    all_records = _execute_manifest_checks(
        manifest,
        resolved_repository_path,
        base_revision,
        before_snapshot,
        logs_directory,
        progress_callback,
    )
    after_snapshot = capture_candidate_snapshot(resolved_repository_path, base_revision)
    return _build_verification_report(
        manifest, resolved_repository_path, before_snapshot, after_snapshot, all_records
    )


def _require_repository_directory(repository_path: Path) -> Path:
    resolved_repository_path = repository_path.resolve()
    if resolved_repository_path.is_dir():
        return resolved_repository_path
    raise ValueError("Repository path must name a directory")


def _execute_manifest_checks(
    manifest: VerificationManifest,
    repository_path: Path,
    base_revision: str,
    before_snapshot: CandidateSnapshot,
    logs_directory: Path,
    progress_callback: ProgressCallback | None,
) -> tuple[CheckRecord, ...]:
    execution_base_revision = before_snapshot.base_revision or base_revision
    return _execute_all_checks(
        manifest,
        repository_path,
        execution_base_revision,
        logs_directory,
        progress_callback,
    )


def _write_report_files(
    report: VerificationReport, logs_directory: Path, report_path: Path
) -> None:
    _write_run_log(report, logs_directory / RUN_LOG_FILENAME)
    _write_report(report, report_path)


def _prepare_logs_directory(report_path: Path) -> Path:
    logs_directory = report_path.resolve().parent / (
        report_path.stem + LOGS_DIRECTORY_SUFFIX
    )
    logs_directory.mkdir(parents=True, exist_ok=True)
    return logs_directory


def _build_verification_report(
    manifest: VerificationManifest,
    repository_path: Path,
    before_snapshot: CandidateSnapshot,
    after_snapshot: CandidateSnapshot,
    all_records: tuple[CheckRecord, ...],
) -> VerificationReport:
    is_worktree_clean = before_snapshot.worktree_clean and after_snapshot.worktree_clean
    is_inputs_unchanged = _inputs_unchanged(before_snapshot, after_snapshot)
    return VerificationReport(
        manifest.version,
        repository_path,
        before_snapshot.base_revision,
        all_records,
        manifest.exclusions,
        before_snapshot.head_revision,
        compute_manifest_digest(manifest),
        is_worktree_clean,
        is_inputs_unchanged,
        _is_publishable(
            all_records,
            before_snapshot,
            after_snapshot,
            is_worktree_clean,
            is_inputs_unchanged,
        ),
    )


def _execute_all_checks(
    manifest: VerificationManifest,
    repository_path: Path,
    base_revision: str,
    logs_directory: Path,
    progress_callback: ProgressCallback | None,
) -> tuple[CheckRecord, ...]:
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


def _inputs_unchanged(
    before_snapshot: CandidateSnapshot, after_snapshot: CandidateSnapshot
) -> bool:
    return (
        before_snapshot.input_digest is not None
        and before_snapshot.input_digest == after_snapshot.input_digest
    )


def _is_publishable(
    all_records: tuple[CheckRecord, ...],
    before_snapshot: CandidateSnapshot,
    after_snapshot: CandidateSnapshot,
    is_worktree_clean: bool,
    is_inputs_unchanged: bool,
) -> bool:
    if not all(each_record.status == PASSED_STATUS for each_record in all_records):
        return False
    return (
        before_snapshot.is_git_repository
        and after_snapshot.is_git_repository
        and before_snapshot.head_revision is not None
        and before_snapshot.head_revision == after_snapshot.head_revision
        and before_snapshot.base_revision is not None
        and before_snapshot.base_revision == after_snapshot.base_revision
        and is_worktree_clean
        and is_inputs_unchanged
    )


def _write_report(report: VerificationReport, report_path: Path) -> None:
    report_mapping = report.as_dict()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report_mapping, indent=JSON_INDENT_SPACES, sort_keys=True)
        + REPORT_NEWLINE,
        encoding=UTF8_ENCODING,
    )


def _write_run_log(report: VerificationReport, run_log_path: Path) -> None:
    all_log_lines = [
        RUN_CHECK_LOG_TEMPLATE.format(
            check_id=each_record.check_id,
            status=each_record.status,
        )
        for each_record in report.checks
    ]
    all_log_lines.extend(
        (
            f"aggregate: {report.aggregate_status}",
            f"head: {report.head_revision}",
            f"base: {report.base_revision}",
            f"worktree_clean: {report.worktree_clean}",
            f"inputs_unchanged: {report.inputs_unchanged}",
            f"publishable: {report.publishable}",
        )
    )
    run_log_path.write_text(
        REPORT_NEWLINE.join(all_log_lines) + REPORT_NEWLINE,
        encoding=UTF8_ENCODING,
    )
