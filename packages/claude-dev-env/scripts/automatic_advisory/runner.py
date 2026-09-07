from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pr_verification.config.constants import LOCAL_CHECKS_PASSED_LABEL
from pr_verification.lock import SupervisorLock
from pr_verification.model import PullRequestCandidate, RepositorySettings

from .checkout import read_local_checkout as _read_local_checkout
from .config.constants import (
    GIT_BASE_REF_TEMPLATE,
    STATE_REASON_BASE_FETCH_FAILED,
    STATE_REASON_CHECKOUT_MISMATCH,
    STATE_REASON_CHILD_INCOMPLETE,
    STATE_REASON_DIRTY_CHECKOUT,
    STATE_REASON_GITHUB_UNAVAILABLE,
    STATE_REASON_PUBLISH_FAILED,
    STATE_REASON_PULL_REQUEST_CLOSED,
    STATE_REASON_UNCHANGED,
    STATE_STATUS_CLOSED,
    STATE_STATUS_ERROR,
    STATE_STATUS_OFFLINE,
    STATE_STATUS_PASSED,
    STATE_STATUS_WAITING,
)
from .execution import _child_produced_report, run_verification_child
from .git import _fetch_base
from .model import (
    AdvisoryRegistration,
    AdvisorySettings,
    AdvisoryState,
    ChildOutcome,
    candidate_identity_matches_state,
)
from .publisher import Publication, _cache_status_for_publication, _publish_report
from .state import _utc_timestamp
from .state import read_state as _read_state
from .state import write_state as _write_state


class AdvisoryGitHub(Protocol):
    def list_open_candidates(
        self,
        repository: RepositorySettings,
        *,
        should_require_merge_commit: bool = True,
    ) -> tuple[PullRequestCandidate, ...]: ...

    def remove_label(
        self, repository: RepositorySettings, pull_request_number: int, label: str
    ) -> None: ...


AdvisoryPublisher = Callable[
    [object, RepositorySettings, int, Path, Path, Path], Publication
]
ChildRunner = Callable[[AdvisoryRegistration, str, float], ChildOutcome]
AdvisoryGitHubFactory = Callable[[RepositorySettings], AdvisoryGitHub]
Clock = Callable[[], str]


class AutomaticAdvisoryRunner:
    def __init__(
        self,
        settings: AdvisorySettings,
        github: AdvisoryGitHub | None,
        *,
        child_runner: ChildRunner | None = None,
        publisher: AdvisoryPublisher | None = None,
        github_factory: AdvisoryGitHubFactory | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.settings = settings
        self.github = github
        self.child_runner = child_runner or run_verification_child
        self.publisher = publisher or _publish_report
        if github_factory is not None:
            self.github_factory = github_factory
        elif github is not None:
            self.github_factory = lambda _repository: github
        else:
            self.github_factory = _github_is_unavailable
        self.clock = clock or _utc_timestamp

    def run_once(self, should_rerun: bool = False) -> tuple[AdvisoryState, ...]:
        """Run each registration once and return its persisted state.

        Args:
            should_rerun: True to force a fresh run for every registration.

        Returns:
            The persisted state of each registration, in settings order.
        """
        return tuple(
            self.run_registration(each_registration, should_rerun)
            for each_registration in self.settings.registrations
        )

    def run_registration(
        self,
        registration: AdvisoryRegistration,
        should_rerun: bool,
    ) -> AdvisoryState:
        with SupervisorLock(registration.repository_lock_root):
            return self._run_registration_locked(registration, should_rerun)

    def _run_registration_locked(
        self,
        registration: AdvisoryRegistration,
        should_rerun: bool,
    ) -> AdvisoryState:
        github_or_state = self._get_github(registration)
        if isinstance(github_or_state, AdvisoryState):
            return github_or_state
        github = github_or_state
        candidate_or_state = self._discover_candidate(registration, github)
        if isinstance(candidate_or_state, AdvisoryState):
            return candidate_or_state
        maybe_previous_state = _read_state(registration.state_path)
        maybe_invalidation_state = self._invalidate_changed_identity(
            registration, candidate_or_state, maybe_previous_state, github
        )
        if maybe_invalidation_state is not None:
            return maybe_invalidation_state
        maybe_blocked_state = self._prepare_candidate(registration, candidate_or_state)
        if maybe_blocked_state is not None:
            return maybe_blocked_state
        return self._run_ready_candidate(
            registration,
            candidate_or_state,
            maybe_previous_state,
            should_rerun,
        )

    def _get_github(
        self, registration: AdvisoryRegistration
    ) -> AdvisoryGitHub | AdvisoryState:
        try:
            return self.github_factory(registration.repository)
        except (OSError, RuntimeError):
            return self._save_state(
                registration,
                STATE_STATUS_OFFLINE,
                STATE_REASON_GITHUB_UNAVAILABLE,
                None,
                None,
            )

    def _discover_candidate(
        self, registration: AdvisoryRegistration, github: AdvisoryGitHub
    ) -> PullRequestCandidate | AdvisoryState:
        try:
            maybe_candidate = self._find_open_candidate(registration, github)
        except (OSError, RuntimeError):
            return self._save_state(
                registration,
                STATE_STATUS_OFFLINE,
                STATE_REASON_GITHUB_UNAVAILABLE,
                None,
                None,
            )
        if maybe_candidate is None:
            if not self._remove_pass_label_safely(registration, github):
                return self._save_state(
                    registration,
                    STATE_STATUS_ERROR,
                    STATE_REASON_PUBLISH_FAILED,
                    None,
                    None,
                )
            return self._save_state(
                registration,
                STATE_STATUS_CLOSED,
                STATE_REASON_PULL_REQUEST_CLOSED,
                None,
                None,
            )
        return maybe_candidate

    def _run_ready_candidate(
        self,
        registration: AdvisoryRegistration,
        candidate: PullRequestCandidate,
        maybe_previous_state: AdvisoryState | None,
        should_rerun: bool,
    ) -> AdvisoryState:
        if (
            not should_rerun
            and maybe_previous_state is not None
            and candidate_identity_matches_state(candidate, maybe_previous_state)
        ):
            return self._save_state(
                registration,
                maybe_previous_state.status,
                STATE_REASON_UNCHANGED,
                candidate,
                maybe_previous_state.last_run,
            )
        return self._execute_and_publish(registration, candidate)

    def _invalidate_changed_identity(
        self,
        registration: AdvisoryRegistration,
        candidate: PullRequestCandidate,
        maybe_previous_state: AdvisoryState | None,
        github: AdvisoryGitHub,
    ) -> AdvisoryState | None:
        if (
            maybe_previous_state is not None
            and maybe_previous_state.status == STATE_STATUS_PASSED
            and candidate_identity_matches_state(candidate, maybe_previous_state)
        ):
            return None
        if self._remove_pass_label_safely(registration, github):
            return None
        return self._save_state(
            registration,
            STATE_STATUS_ERROR,
            STATE_REASON_PUBLISH_FAILED,
            candidate,
            None,
        )

    def _execute_and_publish(
        self,
        registration: AdvisoryRegistration,
        candidate: PullRequestCandidate,
    ) -> AdvisoryState:
        maybe_child_state = self._run_child(registration, candidate)
        if maybe_child_state is not None:
            return maybe_child_state
        try:
            fresh_github = self.github_factory(registration.repository)
        except (OSError, RuntimeError):
            return self._save_state(
                registration,
                STATE_STATUS_OFFLINE,
                STATE_REASON_GITHUB_UNAVAILABLE,
                candidate,
                self.clock(),
            )
        return self._publish_and_save(
            registration,
            candidate,
            fresh_github,
        )

    def _run_child(
        self,
        registration: AdvisoryRegistration,
        candidate: PullRequestCandidate,
    ) -> AdvisoryState | None:
        child_outcome = self.child_runner(
            registration,
            GIT_BASE_REF_TEMPLATE.format(pull_request=registration.pull_request_number),
            self.settings.child_timeout_seconds,
        )
        if _child_produced_report(child_outcome, registration):
            return None
        return self._save_state(
            registration,
            STATE_STATUS_ERROR,
            STATE_REASON_CHILD_INCOMPLETE,
            candidate,
            self.clock(),
        )

    def _prepare_candidate(
        self,
        registration: AdvisoryRegistration,
        candidate: PullRequestCandidate,
    ) -> AdvisoryState | None:
        if not _fetch_base(registration, candidate):
            return self._save_state(
                registration,
                STATE_STATUS_OFFLINE,
                STATE_REASON_BASE_FETCH_FAILED,
                candidate,
                None,
            )
        return self._check_local_checkout(registration, candidate)

    def _check_local_checkout(
        self,
        registration: AdvisoryRegistration,
        candidate: PullRequestCandidate,
    ) -> AdvisoryState | None:
        local_checkout = _read_local_checkout(registration.checkout_path)
        if not local_checkout.is_clean:
            return self._save_state(
                registration,
                STATE_STATUS_WAITING,
                STATE_REASON_DIRTY_CHECKOUT,
                candidate,
                None,
            )
        if local_checkout.head_sha != candidate.head_sha:
            return self._save_state(
                registration,
                STATE_STATUS_WAITING,
                STATE_REASON_CHECKOUT_MISMATCH,
                candidate,
                None,
            )
        return None

    def _remove_pass_label_safely(
        self, registration: AdvisoryRegistration, github: AdvisoryGitHub
    ) -> bool:
        try:
            self._remove_pass_label(registration, github)
        except (OSError, RuntimeError):
            return False
        return True

    def _find_open_candidate(
        self, registration: AdvisoryRegistration, github: AdvisoryGitHub
    ) -> PullRequestCandidate | None:
        all_candidates = github.list_open_candidates(
            registration.repository,
            should_require_merge_commit=False,
        )
        return next(
            (
                each_candidate
                for each_candidate in all_candidates
                if each_candidate.pull_request_number
                == registration.pull_request_number
            ),
            None,
        )

    def _remove_pass_label(
        self, registration: AdvisoryRegistration, github: AdvisoryGitHub
    ) -> None:
        github.remove_label(
            registration.repository,
            registration.pull_request_number,
            LOCAL_CHECKS_PASSED_LABEL,
        )

    def _publish_and_save(
        self,
        registration: AdvisoryRegistration,
        candidate: PullRequestCandidate,
        github: AdvisoryGitHub,
    ) -> AdvisoryState:
        try:
            publication = self.publisher(
                github,
                registration.repository,
                registration.pull_request_number,
                registration.checkout_path,
                registration.selected_manifest_path,
                registration.report_path,
            )
        except (OSError, RuntimeError):
            return self._save_state(
                registration,
                STATE_STATUS_ERROR,
                STATE_REASON_PUBLISH_FAILED,
                candidate,
                self.clock(),
            )
        return self._save_state(
            registration,
            _cache_status_for_publication(publication.status),
            publication.description,
            candidate,
            self.clock(),
        )

    def _save_state(
        self,
        registration: AdvisoryRegistration,
        status: str,
        reason: str,
        maybe_candidate: PullRequestCandidate | None,
        maybe_last_run: str | None,
    ) -> AdvisoryState:
        state = AdvisoryState(
            registration.repository.slug,
            registration.pull_request_number,
            status,
            reason,
            maybe_candidate.head_sha if maybe_candidate else None,
            maybe_candidate.base_sha if maybe_candidate else None,
            self.clock(),
            maybe_last_run,
            str(registration.report_path),
        )
        _write_state(registration.state_path, state)
        return state


def _github_is_unavailable(_repository: RepositorySettings) -> AdvisoryGitHub:
    raise RuntimeError("GitHub client factory is unavailable")
