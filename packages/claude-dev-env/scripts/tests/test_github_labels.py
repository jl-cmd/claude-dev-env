from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from pr_verification.github_labels import remove_label_if_present
from pr_verification.model import RepositorySettings

PASS_LABEL = "local-checks:passed"
FULL_PAGE_SIZE = 100


def repository_settings() -> RepositorySettings:
    return RepositorySettings(
        slug="owner/repository",
        clone_url="https://github.test/owner/repository.git",
    )


def label_page(all_label_names: list[str]) -> list[dict[str, str]]:
    return [{"name": each_label_name} for each_label_name in all_label_names]


class RecordingLabelReader:
    def __init__(self, all_pages: list[object]) -> None:
        self.all_pages = all_pages
        self.all_endpoints: list[str] = []

    def __call__(self, endpoint: str) -> object:
        self.all_endpoints.append(endpoint)
        return self.all_pages.pop(0)


class RecordingLabelDeleter:
    def __init__(self) -> None:
        self.all_endpoints: list[str] = []

    def __call__(self, endpoint: str) -> None:
        self.all_endpoints.append(endpoint)


def test_removes_a_label_a_later_page_holds() -> None:
    all_first_page_names = [
        f"topic-{each_index}" for each_index in range(FULL_PAGE_SIZE)
    ]
    read_labels_page = RecordingLabelReader(
        [label_page(all_first_page_names), label_page([PASS_LABEL])]
    )
    delete_label = RecordingLabelDeleter()

    remove_label_if_present(
        read_labels_page, delete_label, repository_settings(), 7, PASS_LABEL
    )

    assert read_labels_page.all_endpoints == [
        "/repos/owner/repository/issues/7/labels?per_page=100&page=1",
        "/repos/owner/repository/issues/7/labels?per_page=100&page=2",
    ]
    assert delete_label.all_endpoints == [
        "/repos/owner/repository/issues/7/labels/local-checks%3Apassed"
    ]


def test_reads_one_page_when_a_short_page_lacks_the_label() -> None:
    read_labels_page = RecordingLabelReader([label_page(["topic"])])
    delete_label = RecordingLabelDeleter()

    remove_label_if_present(
        read_labels_page, delete_label, repository_settings(), 7, PASS_LABEL
    )

    assert len(read_labels_page.all_endpoints) == 1
    assert delete_label.all_endpoints == []


def test_reads_one_page_when_the_first_page_holds_the_label() -> None:
    read_labels_page = RecordingLabelReader([label_page([PASS_LABEL])])
    delete_label = RecordingLabelDeleter()

    remove_label_if_present(
        read_labels_page, delete_label, repository_settings(), 7, PASS_LABEL
    )

    assert len(read_labels_page.all_endpoints) == 1
    assert len(delete_label.all_endpoints) == 1


def test_reads_no_further_page_when_a_page_is_not_a_list() -> None:
    read_labels_page = RecordingLabelReader([{"message": "Not Found"}])
    delete_label = RecordingLabelDeleter()

    remove_label_if_present(
        read_labels_page, delete_label, repository_settings(), 7, PASS_LABEL
    )

    assert len(read_labels_page.all_endpoints) == 1
    assert delete_label.all_endpoints == []
