from __future__ import annotations

import urllib.parse
from collections.abc import Callable

from .config.constants import (
    GITHUB_PAGE_SIZE,
    ISSUE_LABEL_ENDPOINT_TEMPLATE,
    ISSUE_LABELS_PAGE_ENDPOINT_TEMPLATE,
)
from .model import RepositorySettings

ReadLabelsPage = Callable[[str], object]
DeleteLabel = Callable[[str], None]


def _label_is_present(all_labels: object, label: str) -> bool:
    if not isinstance(all_labels, list):
        return False
    return any(
        isinstance(each_label, dict) and each_label.get("name") == label
        for each_label in all_labels
    )


def _label_page_endpoint(
    repository: RepositorySettings, pull_request_number: int, page: int
) -> str:
    return ISSUE_LABELS_PAGE_ENDPOINT_TEMPLATE.format(
        repository=repository.slug,
        pull_number=pull_request_number,
        page_size=GITHUB_PAGE_SIZE,
        page=page,
    )


def _issue_label_endpoint(
    repository: RepositorySettings, pull_request_number: int, label: str
) -> str:
    return ISSUE_LABEL_ENDPOINT_TEMPLATE.format(
        repository=repository.slug,
        pull_number=pull_request_number,
        label=urllib.parse.quote(label, safe=""),
    )


def _label_is_on_any_page(
    read_labels_page: ReadLabelsPage,
    repository: RepositorySettings,
    pull_request_number: int,
    label: str,
) -> bool:
    page = 1
    while True:
        raw_page = read_labels_page(
            _label_page_endpoint(repository, pull_request_number, page)
        )
        if _label_is_present(raw_page, label):
            return True
        if not isinstance(raw_page, list) or len(raw_page) < GITHUB_PAGE_SIZE:
            return False
        page += 1


def remove_label_if_present(
    read_labels_page: ReadLabelsPage,
    delete_label: DeleteLabel,
    repository: RepositorySettings,
    pull_request_number: int,
    label: str,
) -> None:
    """Delete one label from a pull request when a label page still carries it.

    GitHub returns labels one page at a time, so a pull request carrying more
    labels than one page holds can keep the label on a later page. The walk reads
    pages until it finds the label or reads a short page.

    Args:
        read_labels_page: Reads one labels endpoint and returns its parsed body.
        delete_label: Deletes the label the endpoint names.
        repository: Repository holding the pull request.
        pull_request_number: Pull request number.
        label: Label to remove.
    """
    if not _label_is_on_any_page(
        read_labels_page, repository, pull_request_number, label
    ):
        return
    delete_label(_issue_label_endpoint(repository, pull_request_number, label))
