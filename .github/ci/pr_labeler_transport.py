"""GitHub API transport for `pr_labeler.py`.

::

    ok:   call_api=call_github_api (default)  -> a real GitHub API request
    ok:   call_api=recording_fake (in tests)   -> no network, calls recorded

The only network calls in the labeler live here, made with `urllib.request`
and a bearer token. The module uses the standard library and keeps every
network boundary injectable for focused tests. Every function that reaches the network takes the request-
performing callable as a parameter defaulting to the real one, so callers can
inject a recording fake in tests without touching the network.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, Self

_repo_root_path = str(Path(__file__).resolve().parents[2])
if _repo_root_path not in sys.path:
    sys.path.insert(0, _repo_root_path)

from pr_labeler_derivation import LabelDiff, PullRequestSnapshot, coerce_to_int

from config.pr_labeler_constants import (
    DEFAULT_BRANCH_NAME_FALLBACK,
    FAILURE_DETAIL_JOIN_SEPARATOR,
    GITHUB_API_BASE_URL,
    GITHUB_API_REQUEST_TIMEOUT_SECONDS,
    GITHUB_API_VERSION_HEADER,
    HTTP_STATUS_NOT_FOUND,
    ISSUE_LABEL_DELETE_URL_TEMPLATE,
    ISSUE_LABELS_URL_TEMPLATE,
    PULL_REQUEST_DETAIL_URL_TEMPLATE,
    PULL_REQUEST_FILES_PAGE_SIZE,
    PULL_REQUEST_FILES_PAGE_URL_TEMPLATE,
)


class GitHubApiError(Exception):
    """A GitHub API request failed with a non-2xx HTTP status.

    ::

        ok:   404 on a label DELETE   -> caller may treat it as already-removed
        flag: 403 on a GET or POST    -> caller should surface the failure

    Args:
        status_code: The HTTP status code the API returned.
        failure_detail_text: The raw response body text, for diagnostics.
    """

    def __init__(self, status_code: int, failure_detail_text: str) -> None:
        super().__init__(
            f"GitHub API request failed with status {status_code}: {failure_detail_text}"
        )
        self.status_code = status_code
        self.failure_detail_text = failure_detail_text


def build_github_api_request(
    url: str, github_token: str, http_method: str, json_payload: object | None = None
) -> urllib.request.Request:
    """Build a bearer-authenticated GitHub API request, JSON-encoding the body when given.

    Args:
        url: The full GitHub API URL to request.
        github_token: The bearer token for the Authorization header.
        http_method: The HTTP method (GET, POST, DELETE, ...).
        json_payload: The request body to JSON-encode, or None for no body.

    Returns:
        The constructed `urllib.request.Request`.
    """
    request_headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION_HEADER,
    }
    request_body = None
    if json_payload is not None:
        request_body = json.dumps(json_payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=request_body, headers=request_headers, method=http_method)


class GithubApiConnection(Protocol):
    def read(self) -> bytes: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc_info: object) -> bool | None: ...


def _open_github_api_url(api_request: urllib.request.Request) -> GithubApiConnection:
    """The one line that touches the network: urlopen with the fixed request timeout.

    ``urlopen``'s stub return type is untyped (``Any``); the real object it
    returns satisfies ``GithubApiConnection`` at runtime (``read()`` plus the
    context-manager protocol), so the ignore below covers a stub gap only.
    """
    return urllib.request.urlopen(  # type: ignore[no-any-return]  # stub returns Any; satisfies GithubApiConnection
        api_request, timeout=GITHUB_API_REQUEST_TIMEOUT_SECONDS
    )


def call_github_api(
    url: str,
    github_token: str,
    http_method: str = "GET",
    json_payload: object | None = None,
    open_url: Callable[[urllib.request.Request], GithubApiConnection] = _open_github_api_url,
) -> object:
    """Call the GitHub API and return the parsed JSON body, or None for an empty body.

    Args:
        url: The full GitHub API URL to request.
        github_token: The bearer token for the Authorization header.
        http_method: The HTTP method (GET, POST, DELETE, ...).
        json_payload: The request body to JSON-encode, or None for no body.
        open_url: The connection opener, overridable for tests.

    Returns:
        The parsed JSON body, or None when the response body is empty.

    Raises:
        GitHubApiError: The API returned a non-2xx status, carrying the
            status code and response body for the caller to inspect.
    """
    api_request = build_github_api_request(url, github_token, http_method, json_payload)
    try:
        with open_url(api_request) as api_connection:
            payload_bytes = api_connection.read()
    except urllib.error.HTTPError as http_error:
        failure_detail_text = http_error.read().decode("utf-8", errors="replace")
        raise GitHubApiError(http_error.code, failure_detail_text) from http_error
    if not payload_bytes:
        return None
    return json.loads(payload_bytes.decode("utf-8"))


GitHubApiCaller = Callable[[str, str, str, object | None], object]


def fetch_pull_request_detail(
    repository: str,
    pull_request_number: int,
    github_token: str,
    call_api: GitHubApiCaller = call_github_api,
) -> dict[str, object]:
    """Fetch the raw PR detail: title, draft state, base ref, additions, deletions, labels.

    Args:
        repository: The `owner/name` repository slug.
        pull_request_number: The pull request number.
        github_token: The bearer token for the Authorization header.
        call_api: The GitHub API transport, overridable for tests.

    Returns:
        The raw PR-detail JSON object from the GitHub API.
    """
    url = PULL_REQUEST_DETAIL_URL_TEMPLATE % (GITHUB_API_BASE_URL, repository, pull_request_number)
    pull_request_detail = call_api(url, github_token, "GET", None)
    assert isinstance(pull_request_detail, dict)
    return pull_request_detail


def fetch_all_changed_file_paths(
    repository: str,
    pull_request_number: int,
    github_token: str,
    call_api: GitHubApiCaller = call_github_api,
) -> tuple[str, ...]:
    """Fetch every changed file path, paginating past the 100-file-per-page API cap.

    Args:
        repository: The `owner/name` repository slug.
        pull_request_number: The pull request number.
        github_token: The bearer token for the Authorization header.
        call_api: The GitHub API transport, overridable for tests.

    Returns:
        Every changed file path, across as many pages as the PR needs.
    """
    all_changed_file_paths: list[str] = []
    page_number = 1
    while True:
        url = PULL_REQUEST_FILES_PAGE_URL_TEMPLATE % (
            GITHUB_API_BASE_URL,
            repository,
            pull_request_number,
            PULL_REQUEST_FILES_PAGE_SIZE,
            page_number,
        )
        page_of_files = call_api(url, github_token, "GET", None)
        assert isinstance(page_of_files, list)
        all_changed_file_paths.extend(each_file["filename"] for each_file in page_of_files)
        if len(page_of_files) < PULL_REQUEST_FILES_PAGE_SIZE:
            break
        page_number += 1
    return tuple(all_changed_file_paths)


def extract_current_labels(all_pull_request_detail: dict[str, object]) -> frozenset[str]:
    raw_labels = all_pull_request_detail.get("labels", [])
    assert isinstance(raw_labels, list)
    return frozenset(each_label["name"] for each_label in raw_labels)


def default_branch_name_from_base_ref(all_base_ref_fields: dict[str, object]) -> str:
    """Read the repo's default branch from `base.repo.default_branch`.

    ::

        ok:   base={"repo": {"default_branch": "develop"}}  -> "develop"
        flag: base={"repo": {}} (field missing)              -> "main" (fallback)

    Args:
        all_base_ref_fields: The `base` object from a pull-request-detail response.

    Returns:
        The repository's default branch name, or the fallback when the
        field or its enclosing `repo` object is missing.
    """
    base_repo_info = all_base_ref_fields.get("repo")
    if not isinstance(base_repo_info, dict):
        return DEFAULT_BRANCH_NAME_FALLBACK
    return str(base_repo_info.get("default_branch", DEFAULT_BRANCH_NAME_FALLBACK))


def build_pull_request_snapshot(
    all_pull_request_detail: dict[str, object], all_changed_file_paths: tuple[str, ...]
) -> PullRequestSnapshot:
    """Build the pure `PullRequestSnapshot` derivation input from raw API data.

    Args:
        all_pull_request_detail: The raw PR-detail JSON object from the GitHub API.
        all_changed_file_paths: Every path the pull request changed.

    Returns:
        The `PullRequestSnapshot` `compute_label_diff` derives labels from.
    """
    all_base_ref_fields = all_pull_request_detail["base"]
    assert isinstance(all_base_ref_fields, dict)
    return PullRequestSnapshot(
        title=str(all_pull_request_detail["title"]),
        is_draft=bool(all_pull_request_detail["draft"]),
        base_branch_name=str(all_base_ref_fields["ref"]),
        default_branch_name=default_branch_name_from_base_ref(all_base_ref_fields),
        changed_line_count=coerce_to_int(all_pull_request_detail["additions"])
        + coerce_to_int(all_pull_request_detail["deletions"]),
        changed_file_paths=all_changed_file_paths,
        current_labels=extract_current_labels(all_pull_request_detail),
    )


def fetch_pull_request_snapshot(
    repository: str,
    pull_request_number: int,
    github_token: str,
    call_api: GitHubApiCaller = call_github_api,
) -> PullRequestSnapshot:
    """Fetch the PR detail and its changed file paths, and combine them into a snapshot.

    Args:
        repository: The `owner/name` repository slug.
        pull_request_number: The pull request number.
        github_token: The bearer token for the Authorization header.
        call_api: The GitHub API transport, overridable for tests.

    Returns:
        The `PullRequestSnapshot` `compute_label_diff` derives labels from.
    """
    pull_request_detail = fetch_pull_request_detail(
        repository, pull_request_number, github_token, call_api
    )
    all_changed_file_paths = fetch_all_changed_file_paths(
        repository, pull_request_number, github_token, call_api
    )
    return build_pull_request_snapshot(pull_request_detail, all_changed_file_paths)


def add_labels_to_pull_request(
    repository: str,
    pull_request_number: int,
    github_token: str,
    all_labels_to_add: frozenset[str],
    call_api: GitHubApiCaller = call_github_api,
) -> object:
    """POST the given labels onto the pull request, or do nothing when there are none.

    Args:
        repository: The `owner/name` repository slug.
        pull_request_number: The pull request number.
        github_token: The bearer token for the Authorization header.
        all_labels_to_add: The label names to add.
        call_api: The GitHub API transport, overridable for tests.

    Returns:
        The API response, or None when there was nothing to add.
    """
    if not all_labels_to_add:
        return None
    url = ISSUE_LABELS_URL_TEMPLATE % (GITHUB_API_BASE_URL, repository, pull_request_number)
    return call_api(url, github_token, "POST", {"labels": sorted(all_labels_to_add)})


def remove_label_from_pull_request(
    repository: str,
    pull_request_number: int,
    github_token: str,
    label_name: str,
    call_api: GitHubApiCaller = call_github_api,
) -> object:
    """DELETE one label from the pull request.

    Args:
        repository: The `owner/name` repository slug.
        pull_request_number: The pull request number.
        github_token: The bearer token for the Authorization header.
        label_name: The exact label name to remove.
        call_api: The GitHub API transport, overridable for tests.

    Returns:
        The API response.
    """
    encoded_label_name = urllib.parse.quote(label_name, safe="")
    url = ISSUE_LABEL_DELETE_URL_TEMPLATE % (
        GITHUB_API_BASE_URL,
        repository,
        pull_request_number,
        encoded_label_name,
    )
    return call_api(url, github_token, "DELETE", None)


def apply_label_diff(
    repository: str,
    pull_request_number: int,
    github_token: str,
    label_diff: LabelDiff,
    call_api: GitHubApiCaller = call_github_api,
) -> None:
    """Add every label the diff wants, then remove every label the diff drops.

    Each removal is guarded on its own: a 404 means the label is already
    gone (another run beat this one to it), so that one label is skipped
    and every other removal is still attempted. Any other failure is
    collected and re-raised once the loop finishes, so one bad label never
    strands the rest of the removals behind it.

    Args:
        repository: The `owner/name` repository slug.
        pull_request_number: The pull request number.
        github_token: The bearer token for the Authorization header.
        label_diff: The labels to add and the labels to remove.
        call_api: The GitHub API transport, overridable for tests.

    Raises:
        GitHubApiError: At least one removal failed with a status other
            than 404, after every removal was attempted.
    """
    add_labels_to_pull_request(
        repository, pull_request_number, github_token, label_diff.labels_to_add, call_api
    )
    all_removal_errors: list[GitHubApiError] = []
    for each_label_name in sorted(label_diff.labels_to_remove):
        try:
            remove_label_from_pull_request(
                repository, pull_request_number, github_token, each_label_name, call_api
            )
        except GitHubApiError as removal_error:
            if removal_error.status_code == HTTP_STATUS_NOT_FOUND:
                continue
            all_removal_errors.append(removal_error)
    if all_removal_errors:
        combined_failure_detail_text = FAILURE_DETAIL_JOIN_SEPARATOR.join(
            f"{each_error.status_code}: {each_error.failure_detail_text}"
            for each_error in all_removal_errors
        )
        raise GitHubApiError(all_removal_errors[0].status_code, combined_failure_detail_text)
