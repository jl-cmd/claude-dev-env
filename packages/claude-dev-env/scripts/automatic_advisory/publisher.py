from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Protocol

from pr_verification.config.constants import STATUS_FAILURE, STATUS_SUCCESS
from pr_verification.model import RepositorySettings

from .config.constants import STATE_STATUS_FAILED, STATE_STATUS_PASSED


class Publication(Protocol):
    @property
    def status(self) -> str: ...

    @property
    def description(self) -> str: ...


class PublicationStatus(Protocol):
    @property
    def value(self) -> str: ...


class PublisherOutcome(Protocol):
    @property
    def status(self) -> PublicationStatus: ...

    @property
    def description(self) -> str: ...


@dataclass(frozen=True)
class PublicationRecord:
    status: str
    description: str


def _publish_report(
    github: object,
    repository: RepositorySettings,
    pull_request_number: int,
    checkout_path: Path,
    manifest_path: Path,
    report_path: Path,
) -> Publication:
    publisher_module = import_module("local_report_publisher")
    publisher_function: Callable[..., PublisherOutcome] = (
        publisher_module.publish_local_report
    )
    publication_outcome = publisher_function(
        github,
        repository,
        pull_request_number,
        checkout_path,
        manifest_path,
        report_path,
    )
    publication_status = publication_outcome.status
    publication_description = publication_outcome.description
    return PublicationRecord(
        _normalize_publication_status(publication_status),
        publication_description,
    )


def _normalize_publication_status(publication_status: PublicationStatus) -> str:
    status_text = publication_status.value
    if status_text == STATUS_SUCCESS:
        return STATUS_SUCCESS
    if status_text == STATUS_FAILURE:
        return STATUS_FAILURE
    return status_text


def _cache_status_for_publication(publication_status: str) -> str:
    if publication_status == STATUS_SUCCESS:
        return STATE_STATUS_PASSED
    if publication_status == STATUS_FAILURE:
        return STATE_STATUS_FAILED
    return publication_status
