from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from local_report_validation import (
    ReportDecision,
    _load_all_report_fields,
    _matches_candidate,
    _validate_report,
)
from local_verification.git_state import CandidateSnapshot, capture_candidate_snapshot
from local_verification.manifest import ManifestRunFatal, load_manifest
from local_verification.model import VerificationManifest
from pr_verification.config.constants import (
    ERROR_DESCRIPTION,
    LOCAL_CHECKS_CONTEXT,
    LOCAL_CHECKS_PASSED_LABEL,
    PENDING_DESCRIPTION,
)
from pr_verification.github import GitHubApi
from pr_verification.model import (
    PullRequestCandidate,
    RepositorySettings,
    StatusState,
)


@dataclass(frozen=True)
class PublicationOutcome:
    status: StatusState
    description: str
    publishable: bool


def publish_local_report(
    github: GitHubApi,
    repository: RepositorySettings,
    pull_request_number: int,
    local_repository_path: Path,
    manifest_path: Path,
    report_path: Path,
) -> PublicationOutcome:
    """Publish one local report.

    Args:
        github: GitHub API client.
        repository: Repository settings.
        pull_request_number: Pull request number that owns the report.
        local_repository_path: Local checkout that produced the report.
        manifest_path: Verification manifest path.
        report_path: Verification report path.

    Returns:
        The publication outcome.
    """
    return _publish_report_inputs(
        github,
        repository,
        pull_request_number,
        local_repository_path,
        _load_report_inputs(manifest_path, report_path),
    )


def _publish_report_inputs(
    github: GitHubApi,
    repository: RepositorySettings,
    pull_request_number: int,
    local_repository_path: Path,
    all_report_inputs: tuple[VerificationManifest, Mapping[str, object]] | None,
) -> PublicationOutcome:
    candidate = github.get_candidate(
        repository, pull_request_number, should_require_merge_commit=False
    )
    if all_report_inputs is None:
        return _publish_advisory(
            github, repository, candidate, StatusState.PENDING, PENDING_DESCRIPTION
        )
    manifest, all_report_fields = all_report_inputs
    return _publish_loaded_report(
        github,
        repository,
        pull_request_number,
        local_repository_path,
        manifest,
        all_report_fields,
        candidate,
    )


def _load_report_inputs(
    manifest_path: Path, report_path: Path
) -> tuple[VerificationManifest, Mapping[str, object]] | None:
    try:
        manifest = load_manifest(manifest_path)
        all_report_fields = _load_all_report_fields(report_path)
    except (
        ManifestRunFatal,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return None
    return manifest, all_report_fields


def _publish_loaded_report(
    github: GitHubApi,
    repository: RepositorySettings,
    pull_request_number: int,
    local_repository_path: Path,
    manifest: VerificationManifest,
    all_report_fields: Mapping[str, object],
    candidate: PullRequestCandidate,
) -> PublicationOutcome:
    decision = _validate_report(
        manifest, all_report_fields, candidate, local_repository_path
    )
    if not decision.publishable:
        return _publish_advisory(
            github, repository, candidate, decision.status, decision.description
        )
    return _publish_success(
        github,
        repository,
        pull_request_number,
        local_repository_path,
        candidate,
        decision,
    )


def _publish_advisory(
    github: GitHubApi,
    repository: RepositorySettings,
    candidate: PullRequestCandidate,
    status: StatusState,
    description: str,
) -> PublicationOutcome:
    github.remove_label(
        repository, candidate.pull_request_number, LOCAL_CHECKS_PASSED_LABEL
    )
    github.post_status(
        repository, candidate.head_sha, status, LOCAL_CHECKS_CONTEXT, description
    )
    return PublicationOutcome(status, description, False)


def _publish_success(
    github: GitHubApi,
    repository: RepositorySettings,
    pull_request_number: int,
    local_repository_path: Path,
    candidate: PullRequestCandidate,
    decision: ReportDecision,
) -> PublicationOutcome:
    latest_candidate, latest_snapshot = _read_current_candidate(
        github, repository, pull_request_number, local_repository_path
    )
    if not _matches_candidate(
        latest_snapshot,
        latest_candidate,
        candidate.head_sha,
        candidate.base_sha,
    ):
        return _publish_advisory(
            github, repository, latest_candidate, StatusState.ERROR, ERROR_DESCRIPTION
        )
    _post_success(github, repository, pull_request_number, latest_candidate, decision)
    return _confirm_success(
        github,
        repository,
        pull_request_number,
        local_repository_path,
        latest_candidate,
        decision,
    )


def _read_current_candidate(
    github: GitHubApi,
    repository: RepositorySettings,
    pull_request_number: int,
    local_repository_path: Path,
) -> tuple[PullRequestCandidate, CandidateSnapshot]:
    candidate = github.get_candidate(
        repository, pull_request_number, should_require_merge_commit=False
    )
    snapshot = capture_candidate_snapshot(local_repository_path, candidate.base_sha)
    return candidate, snapshot


def _post_success(
    github: GitHubApi,
    repository: RepositorySettings,
    pull_request_number: int,
    candidate: PullRequestCandidate,
    decision: ReportDecision,
) -> None:
    github.post_status(
        repository,
        candidate.head_sha,
        StatusState.SUCCESS,
        LOCAL_CHECKS_CONTEXT,
        decision.description,
    )
    github.add_label(repository, pull_request_number, LOCAL_CHECKS_PASSED_LABEL)


def _confirm_success(
    github: GitHubApi,
    repository: RepositorySettings,
    pull_request_number: int,
    local_repository_path: Path,
    candidate: PullRequestCandidate,
    decision: ReportDecision,
) -> PublicationOutcome:
    final_candidate, final_snapshot = _read_current_candidate(
        github, repository, pull_request_number, local_repository_path
    )
    if _matches_candidate(
        final_snapshot,
        final_candidate,
        candidate.head_sha,
        candidate.base_sha,
    ):
        return _decision_to_outcome(decision)
    github.remove_label(repository, pull_request_number, LOCAL_CHECKS_PASSED_LABEL)
    github.post_status(
        repository,
        final_candidate.head_sha,
        StatusState.ERROR,
        LOCAL_CHECKS_CONTEXT,
        ERROR_DESCRIPTION,
    )
    return PublicationOutcome(StatusState.ERROR, ERROR_DESCRIPTION, False)


def _decision_to_outcome(decision: ReportDecision) -> PublicationOutcome:
    return PublicationOutcome(
        decision.status, decision.description, decision.publishable
    )
