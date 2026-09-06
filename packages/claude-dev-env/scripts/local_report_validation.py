from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from local_verification.check_support import _substitute_arguments
from local_verification.config import (
    CHECK_FAILED_EXIT_CODE,
    COLLECTION_ERROR_KIND,
    FAILED_STATUS,
    INCOMPLETE_EXIT_CODE,
    INCOMPLETE_STATUS,
    MINIMUM_TESTS_ERROR_KIND,
    PASSED_STATUS,
    SUCCESS_EXIT_CODE,
)
from local_verification.git_state import CandidateSnapshot, capture_candidate_snapshot
from local_verification.manifest import compute_manifest_digest
from local_verification.model import CheckSpec, VerificationManifest
from pr_verification.config.constants import ERROR_DESCRIPTION, FAILURE_DESCRIPTION
from pr_verification.model import PullRequestCandidate, StatusState


@dataclass(frozen=True)
class ReportDecision:
    status: StatusState
    description: str
    publishable: bool
    selected_check_ids: tuple[str, ...] = ()


def _load_all_report_fields(report_path: Path) -> Mapping[str, object]:
    parsed_report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(parsed_report, Mapping):
        raise TypeError("Verification report must be an object")
    return parsed_report


def _validate_report(
    manifest: VerificationManifest,
    all_report_fields: Mapping[str, object],
    candidate: PullRequestCandidate,
    local_repository_path: Path,
) -> ReportDecision:
    report_head = _text_field(all_report_fields, "head")
    report_base = _text_field(all_report_fields, "base")
    if report_head is None or report_base is None:
        return _invalid_report()
    status = _validate_all_check_fields(
        all_report_fields, manifest.checks, local_repository_path, candidate.base_sha
    )
    if status != PASSED_STATUS:
        return _status_decision(status)
    if not _matches_report_metadata(all_report_fields, manifest):
        return _invalid_report()
    snapshot = capture_candidate_snapshot(local_repository_path, report_base)
    if not _matches_candidate(snapshot, candidate, report_head, report_base):
        return _invalid_report()
    check_count = len(manifest.checks)
    return ReportDecision(
        StatusState.SUCCESS,
        f"Selected local checks passed ({check_count} checks)",
        True,
        tuple(each_check.check_id for each_check in manifest.checks),
    )


def _status_decision(status: str | None) -> ReportDecision:
    if status == FAILED_STATUS:
        return ReportDecision(StatusState.FAILURE, FAILURE_DESCRIPTION, False)
    return ReportDecision(StatusState.ERROR, ERROR_DESCRIPTION, False)


def _matches_report_metadata(
    all_report_fields: Mapping[str, object], manifest: VerificationManifest
) -> bool:
    return (
        all_report_fields.get("manifest_digest") == compute_manifest_digest(manifest)
        and all_report_fields.get("publishable") is True
        and all_report_fields.get("worktree_clean") is True
        and all_report_fields.get("inputs_unchanged") is True
    )


def _validate_all_check_fields(
    all_report_fields: Mapping[str, object],
    all_manifest_checks: tuple[CheckSpec, ...],
    local_repository_path: Path,
    base_revision: str,
) -> str | None:
    all_statuses = _read_check_statuses(
        all_report_fields, all_manifest_checks, local_repository_path, base_revision
    )
    if all_statuses is None:
        return None
    return _validate_aggregate(all_report_fields, all_statuses)


def _read_check_statuses(
    all_report_fields: Mapping[str, object],
    all_manifest_checks: tuple[CheckSpec, ...],
    local_repository_path: Path,
    base_revision: str,
) -> list[str] | None:
    raw_checks = all_report_fields.get("checks")
    if not isinstance(raw_checks, list):
        return None
    all_check_ids: list[str] = []
    all_statuses: list[str] = []
    for each_index, each_raw_check in enumerate(raw_checks):
        check_fields = _read_check_fields(
            each_raw_check,
            all_manifest_checks,
            each_index,
            local_repository_path,
            base_revision,
        )
        if check_fields is None:
            return None
        check_id, status = check_fields
        all_check_ids.append(check_id)
        all_statuses.append(status)
    if not _check_records_match_manifest(
        all_check_ids, all_statuses, all_manifest_checks
    ):
        return None
    return all_statuses


def _check_records_match_manifest(
    all_check_ids: list[str],
    all_statuses: list[str],
    all_manifest_checks: tuple[CheckSpec, ...],
) -> bool:
    selected_check_ids = tuple(
        each_check.check_id for each_check in all_manifest_checks
    )
    if tuple(all_check_ids) != selected_check_ids:
        return False
    return all(
        each_status in {PASSED_STATUS, FAILED_STATUS, INCOMPLETE_STATUS}
        for each_status in all_statuses
    )


def _read_check_fields(
    raw_check: object,
    all_manifest_checks: tuple[CheckSpec, ...],
    check_index: int,
    local_repository_path: Path,
    base_revision: str,
) -> tuple[str, str] | None:
    if not isinstance(raw_check, Mapping):
        return None
    check_id = raw_check.get("id")
    status = raw_check.get("status")
    if not isinstance(check_id, str) or not isinstance(status, str):
        return None
    if not _all_check_fields_matches_spec(
        raw_check,
        all_manifest_checks,
        check_index,
        status,
        local_repository_path,
        base_revision,
    ):
        return None
    return check_id, status


def _validate_aggregate(
    all_report_fields: Mapping[str, object], all_statuses: list[str]
) -> str | None:
    aggregate_status = _aggregate_status(all_statuses)
    aggregate_mapping = all_report_fields.get("aggregate")
    if not isinstance(aggregate_mapping, Mapping):
        return None
    if aggregate_mapping.get("status") != aggregate_status:
        return None
    if all_report_fields.get("status") != aggregate_status:
        return None
    expected_exit_code = _status_exit_code(aggregate_status)
    if not _matches_integer(all_report_fields.get("exit_code"), expected_exit_code):
        return None
    expected_counts = {
        "total": len(all_statuses),
        "passed": all_statuses.count(PASSED_STATUS),
        "failed": all_statuses.count(FAILED_STATUS),
        "incomplete": all_statuses.count(INCOMPLETE_STATUS),
        "exit_code": expected_exit_code,
    }
    if any(
        not _matches_integer(aggregate_mapping.get(each_name), each_count)
        for each_name, each_count in expected_counts.items()
    ):
        return None
    return aggregate_status


def _all_check_fields_matches_spec(
    all_check_fields: Mapping[str, object],
    all_manifest_checks: tuple[CheckSpec, ...],
    check_index: int,
    status: str,
    local_repository_path: Path,
    base_revision: str,
) -> bool:
    if check_index >= len(all_manifest_checks):
        return False
    if not _matches_execution_fields(all_check_fields, status):
        return False
    check_spec = all_manifest_checks[check_index]
    if not _matches_command_arguments(
        all_check_fields, check_spec, local_repository_path, base_revision
    ):
        return False
    if not _matches_check_directory(
        all_check_fields, check_spec, local_repository_path
    ):
        return False
    if all_check_fields.get("minimum_tests") != check_spec.minimum_tests:
        return False
    return _matches_collection_fields(all_check_fields, check_spec, status)


def _matches_command_arguments(
    all_check_fields: Mapping[str, object],
    check_spec: CheckSpec,
    local_repository_path: Path,
    base_revision: str,
) -> bool:
    all_recorded_arguments = all_check_fields.get("argv")
    if not isinstance(all_recorded_arguments, list):
        return False
    if any(
        not isinstance(each_argument, str) for each_argument in all_recorded_arguments
    ):
        return False
    expected_arguments = _substitute_arguments(
        check_spec.command_arguments, local_repository_path, base_revision
    )
    return tuple(all_recorded_arguments) == expected_arguments


def _matches_execution_fields(
    all_check_fields: Mapping[str, object], status: str
) -> bool:
    exit_code = all_check_fields.get("exit_code")
    error_kind = all_check_fields.get("error_kind")
    error_message = all_check_fields.get("error_message")
    if status == PASSED_STATUS:
        return (
            exit_code == SUCCESS_EXIT_CODE
            and error_kind is None
            and error_message is None
        )
    if not isinstance(error_kind, str) or not error_kind:
        return False
    if not isinstance(error_message, str) or not error_message:
        return False
    if status == FAILED_STATUS and error_kind == MINIMUM_TESTS_ERROR_KIND:
        return exit_code == SUCCESS_EXIT_CODE
    if status == FAILED_STATUS:
        return _is_integer(exit_code) and exit_code != SUCCESS_EXIT_CODE
    return status == INCOMPLETE_STATUS


def _matches_check_directory(
    all_check_fields: Mapping[str, object],
    check_spec: CheckSpec,
    local_repository_path: Path,
) -> bool:
    expected_check_directory = (local_repository_path / check_spec.cwd).resolve()
    recorded_check_directory = all_check_fields.get("cwd")
    return (
        isinstance(recorded_check_directory, str)
        and Path(recorded_check_directory).resolve() == expected_check_directory
    )


def _matches_collection_fields(
    all_check_fields: Mapping[str, object], check_spec: CheckSpec, status: str
) -> bool:
    if check_spec.minimum_tests is None:
        return True
    collected_tests = _read_integer(all_check_fields.get("collected_tests"))
    collection_exit_code = _read_integer(all_check_fields.get("collection_exit_code"))
    if collected_tests is None or collection_exit_code is None:
        return False
    if status == PASSED_STATUS:
        return (
            collection_exit_code == SUCCESS_EXIT_CODE
            and collected_tests >= check_spec.minimum_tests
        )
    if (
        status == FAILED_STATUS
        and all_check_fields.get("error_kind") == MINIMUM_TESTS_ERROR_KIND
    ):
        return collected_tests < check_spec.minimum_tests
    if all_check_fields.get("error_kind") != COLLECTION_ERROR_KIND:
        return True
    return collection_exit_code != SUCCESS_EXIT_CODE


def _aggregate_status(all_statuses: list[str]) -> str:
    if FAILED_STATUS in all_statuses:
        return FAILED_STATUS
    if INCOMPLETE_STATUS in all_statuses:
        return INCOMPLETE_STATUS
    return PASSED_STATUS


def _status_exit_code(status: str) -> int:
    if status == FAILED_STATUS:
        return CHECK_FAILED_EXIT_CODE
    if status == INCOMPLETE_STATUS:
        return INCOMPLETE_EXIT_CODE
    return SUCCESS_EXIT_CODE


def _matches_candidate(
    candidate_snapshot: CandidateSnapshot,
    candidate: PullRequestCandidate,
    report_head: str,
    report_base: str,
) -> bool:
    return (
        candidate_snapshot.is_git_repository
        and candidate_snapshot.worktree_clean
        and candidate_snapshot.head_revision == report_head == candidate.head_sha
        and candidate_snapshot.base_revision == report_base == candidate.base_sha
    )


def _read_integer(raw_integer: object) -> int | None:
    if isinstance(raw_integer, bool) or not isinstance(raw_integer, int):
        return None
    return raw_integer


def _is_integer(raw_integer: object) -> bool:
    return isinstance(raw_integer, int) and not isinstance(raw_integer, bool)


def _matches_integer(raw_integer: object, expected_integer: int) -> bool:
    return _is_integer(raw_integer) and raw_integer == expected_integer


def _invalid_report() -> ReportDecision:
    return ReportDecision(StatusState.ERROR, ERROR_DESCRIPTION, False)


def _text_field(all_report_fields: Mapping[str, object], field_name: str) -> str | None:
    field_text = all_report_fields.get(field_name)
    return field_text if isinstance(field_text, str) and field_text else None
