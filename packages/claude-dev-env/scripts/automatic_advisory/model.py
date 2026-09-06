from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pr_verification.model import PullRequestCandidate, RepositorySettings

from .config.constants import (
    ALL_TERMINAL_STATUSES,
    POLL_LOCK_DIRECTORY_NAME,
    SELECTED_MANIFEST_SUFFIX,
)


@dataclass(frozen=True)
class AdvisoryRegistration:
    repository: RepositorySettings
    pull_request_number: int
    checkout_path: Path
    manifest_path: PurePosixPath
    report_path: Path
    state_path: Path
    base_ref: str
    remote_name: str

    @property
    def manifest_absolute_path(self) -> Path:
        return self.checkout_path / Path(self.manifest_path)

    @property
    def selected_manifest_path(self) -> Path:
        return self.report_path.with_name(
            self.report_path.stem + SELECTED_MANIFEST_SUFFIX
        )

    @property
    def repository_lock_root(self) -> Path:
        return self.state_path.parent


@dataclass(frozen=True)
class AdvisorySettings:
    api_url: str
    app_id: int
    installation_id: int
    private_key_path: Path
    poll_seconds: float
    child_timeout_seconds: float
    registrations: tuple[AdvisoryRegistration, ...]

    @property
    def poll_lock_root(self) -> Path:
        return self.registrations[0].state_path.parent / POLL_LOCK_DIRECTORY_NAME


@dataclass(frozen=True)
class AdvisoryState:
    repository: str
    pull_request_number: int
    status: str
    reason: str
    head_sha: str | None
    base_sha: str | None
    last_poll: str
    last_run: str | None
    report_path: str


@dataclass(frozen=True)
class ChildOutcome:
    exit_code: int | None
    stdout_text: str
    stderr_text: str
    timed_out: bool


@dataclass(frozen=True)
class LocalCheckout:
    head_sha: str | None
    is_clean: bool


def candidate_identity_matches_state(
    candidate: PullRequestCandidate,
    maybe_state: AdvisoryState | None,
) -> bool:
    """Return whether a terminal state already covers the candidate identity.

    Args:
        candidate: Current remote pull request identity.
        maybe_state: Recorded advisory state.

    Returns:
        True when the same head and base already reached a terminal state.
    """
    if maybe_state is None:
        return False
    return (
        maybe_state.head_sha == candidate.head_sha
        and maybe_state.base_sha == candidate.base_sha
        and maybe_state.status in ALL_TERMINAL_STATUSES
    )
