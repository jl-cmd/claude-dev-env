from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from automatic_advisory.model import (
    AdvisoryRegistration,
    AdvisorySettings,
    AdvisoryState,
)
from automatic_advisory.publisher import Publication
from automatic_advisory.runner import AdvisoryGitHub, AutomaticAdvisoryRunner
from automatic_advisory.state import read_state, write_state
from pr_verification.config.constants import LOCAL_CHECKS_PASSED_LABEL
from pr_verification.model import PullRequestCandidate, RepositorySettings


class ClosedPullRequestGitHub(AdvisoryGitHub):
    def __init__(self, state_path: Path, failed_removal_count: int) -> None:
        self.state_path = state_path
        self.failed_removal_count = failed_removal_count
        self.removed_labels: list[str] = []
        self.observed_statuses: list[str | None] = []

    def list_open_candidates(
        self,
        repository: RepositorySettings,
        *,
        should_require_merge_commit: bool = True,
    ) -> tuple[PullRequestCandidate, ...]:
        return ()

    def remove_label(
        self, repository: RepositorySettings, pull_request_number: int, label: str
    ) -> None:
        maybe_state = read_state(self.state_path)
        self.observed_statuses.append(maybe_state.status if maybe_state else None)
        self.removed_labels.append(label)
        if self.failed_removal_count:
            self.failed_removal_count -= 1
            raise RuntimeError("label service unavailable")


def _build_registration(tmp_path: Path) -> AdvisoryRegistration:
    return AdvisoryRegistration(
        RepositorySettings("JonEcho/python-automation", "unused"),
        3082,
        tmp_path / "checkout",
        PurePosixPath("manifest.json"),
        tmp_path / "report.json",
        tmp_path / "state.json",
        "main",
        "origin",
    )


def _build_runner(
    registration: AdvisoryRegistration,
    github: ClosedPullRequestGitHub,
) -> AutomaticAdvisoryRunner:
    settings = AdvisorySettings(
        "https://api.github.com",
        4841271,
        159293880,
        registration.state_path.with_name("private-key.pem"),
        60.0,
        30.0,
        (registration,),
    )
    return AutomaticAdvisoryRunner(
        settings,
        github,
        child_runner=_unexpected_child,
        publisher=_unexpected_publisher,
        clock=lambda: "2026-09-05T00:00:00+00:00",
    )


def _unexpected_child(
    *all_arguments: object,
    **all_keyword_arguments: object,
) -> object:
    raise AssertionError("closed pull requests must not run checks")


def _unexpected_publisher(*all_arguments: object) -> Publication:
    raise AssertionError("closed pull requests must not publish reports")


def _write_passed_state(registration: AdvisoryRegistration) -> None:
    write_state(
        registration.state_path,
        AdvisoryState(
            registration.repository.slug,
            registration.pull_request_number,
            "passed",
            "local checks passed",
            "old-head",
            "base-head",
            "2026-09-04T00:00:00+00:00",
            "2026-09-09T00:00:00+00:00",
            str(registration.report_path),
        ),
    )


def test_closed_pull_request_removes_stale_label_before_saving_closed_state(
    tmp_path: Path,
) -> None:
    registration = _build_registration(tmp_path)
    _write_passed_state(registration)
    github = ClosedPullRequestGitHub(registration.state_path, 0)
    runner = _build_runner(registration, github)

    state = runner.run_once()[0]

    assert state.status == "closed"
    assert github.removed_labels == [LOCAL_CHECKS_PASSED_LABEL]
    assert github.observed_statuses == ["passed"]
    assert read_state(registration.state_path).status == "closed"


def test_closed_pull_request_retries_failed_label_removal(
    tmp_path: Path,
) -> None:
    registration = _build_registration(tmp_path)
    _write_passed_state(registration)
    github = ClosedPullRequestGitHub(registration.state_path, 1)
    runner = _build_runner(registration, github)

    error_state = runner.run_once()[0]
    closed_state = runner.run_once()[0]

    assert error_state.status == "error"
    assert closed_state.status == "closed"
    assert github.removed_labels == [
        LOCAL_CHECKS_PASSED_LABEL,
        LOCAL_CHECKS_PASSED_LABEL,
    ]
    assert github.observed_statuses == ["passed", "error"]


def test_closed_pull_request_does_not_run_checks(
    tmp_path: Path,
) -> None:
    registration = _build_registration(tmp_path)
    github = ClosedPullRequestGitHub(registration.state_path, 0)
    runner = _build_runner(registration, github)

    state = runner.run_once()[0]

    assert state.status == "closed"
    assert github.removed_labels == [LOCAL_CHECKS_PASSED_LABEL]
