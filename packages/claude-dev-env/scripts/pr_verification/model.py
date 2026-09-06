from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config.constants import (
    STATUS_ERROR,
    STATUS_FAILURE,
    STATUS_PENDING,
    STATUS_SUCCESS,
)


class StatusState(str, Enum):
    PENDING = STATUS_PENDING
    ERROR = STATUS_ERROR
    FAILURE = STATUS_FAILURE
    SUCCESS = STATUS_SUCCESS


@dataclass(frozen=True)
class RepositorySettings:
    slug: str
    clone_url: str

    @property
    def name(self) -> str:
        return self.slug.split("/", maxsplit=1)[1]


@dataclass(frozen=True)
class PullRequestCandidate:
    repository_slug: str
    pull_request_number: int
    base_ref: str
    base_sha: str
    head_sha: str
    merge_sha: str
    is_draft: bool

    @property
    def key(self) -> tuple[str, int]:
        return self.repository_slug, self.pull_request_number
