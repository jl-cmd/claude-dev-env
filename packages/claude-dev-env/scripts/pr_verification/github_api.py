from __future__ import annotations

import json
import urllib.parse

from .branch_refs import (
    GetJson,
    _resolve_candidate_base_shas,
    replace_candidate_base_sha,
)
from .config.constants import (
    ACCEPT_HEADER,
    API_VERSION_HEADER,
    AUTHORIZATION_HEADER,
    BEARER_PREFIX,
    COMMIT_ENDPOINT_TEMPLATE,
    COMMIT_PARENTS_KEY,
    CONTENT_TYPE_HEADER,
    GITHUB_ACCEPT_TYPE,
    GITHUB_API_VERSION,
    GITHUB_JSON_ERROR_TEMPLATE,
    GITHUB_PAGE_SIZE,
    GITHUB_REQUEST_ERROR_TEMPLATE,
    GITHUB_SHAPE_ERROR_TEMPLATE,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_OK,
    ISSUE_LABEL_ENDPOINT_TEMPLATE,
    ISSUE_LABELS_ENDPOINT_TEMPLATE,
    ISSUE_LABELS_KEY,
    JSON_CONTENT_TYPE,
    PULL_ENDPOINT_TEMPLATE,
    PULL_SHA_KEY,
    PULLS_ENDPOINT_TEMPLATE,
    STATUS_CONTEXT_KEY,
    STATUS_DESCRIPTION_KEY,
    STATUS_ENDPOINT_TEMPLATE,
    STATUS_STATE_KEY,
    UTF8_ENCODING,
)
from .github_parsing import (
    GitHubError,
    _parse_pull_candidates,
    _require_pull_list,
    parse_candidate,
    require_mapping,
    require_text,
)
from .github_transport import HttpReply, HttpRequester, request_http
from .model import PullRequestCandidate, RepositorySettings, StatusState


def _build_pull_page_endpoint(repository: RepositorySettings, page: int) -> str:
    return PULLS_ENDPOINT_TEMPLATE.format(
        repository=repository.slug,
        page_size=GITHUB_PAGE_SIZE,
        page=page,
    )


def _build_status_body(state: StatusState, context: str, description: str) -> bytes:
    status_payload = {
        STATUS_STATE_KEY: state.value,
        STATUS_CONTEXT_KEY: context,
        STATUS_DESCRIPTION_KEY: description,
    }
    return json.dumps(status_payload).encode(UTF8_ENCODING)


def _label_is_present(all_labels: object, label: str) -> bool:
    if not isinstance(all_labels, list):
        return False
    return any(
        isinstance(each_label, dict) and each_label.get("name") == label
        for each_label in all_labels
    )


def _remove_label_if_present(
    requester: HttpRequester,
    api_url: str,
    repository: RepositorySettings,
    pull_request_number: int,
    label: str,
    all_headers: dict[str, str],
) -> None:
    labels_endpoint = ISSUE_LABELS_ENDPOINT_TEMPLATE.format(
        repository=repository.slug,
        pull_number=pull_request_number,
    )
    all_labels = request_json(
        requester, "GET", api_url + labels_endpoint, all_headers, None, HTTP_OK
    )
    if not _label_is_present(all_labels, label):
        return
    encoded_label = urllib.parse.quote(label, safe="")
    endpoint = ISSUE_LABEL_ENDPOINT_TEMPLATE.format(
        repository=repository.slug,
        pull_number=pull_request_number,
        label=encoded_label,
    )
    _delete_label(requester, api_url + endpoint, all_headers)


def _list_open_candidates(
    get_json: GetJson,
    repository: RepositorySettings,
    should_require_merge_commit: bool,
) -> tuple[PullRequestCandidate, ...]:
    all_candidates: list[PullRequestCandidate] = []
    page = 1
    while True:
        endpoint = _build_pull_page_endpoint(repository, page)
        raw_page = _require_pull_list(get_json(endpoint))
        all_candidates.extend(
            _parse_pull_candidates(
                repository.slug,
                raw_page,
                should_require_merge_commit,
            )
        )
        if len(raw_page) < GITHUB_PAGE_SIZE:
            return _resolve_candidate_base_shas(
                all_candidates,
                repository,
                get_json,
                should_require_merge_commit,
            )
        page += 1


class GitHubApi:
    def __init__(
        self,
        api_url: str,
        installation_token: str,
        requester: HttpRequester = request_http,
    ) -> None:
        self.api_url = api_url
        self.installation_token = installation_token
        self.requester = requester

    def list_open_candidates(
        self,
        repository: RepositorySettings,
        *,
        should_require_merge_commit: bool = True,
    ) -> tuple[PullRequestCandidate, ...]:
        """List recognized pull requests.

        Args:
            repository: Repository to query.

        Returns:
            Recognized pull requests.

        Raises:
            GitHubError: If GitHub data is invalid.
        """
        return _list_open_candidates(
            self.get_json,
            repository,
            should_require_merge_commit,
        )

    def get_candidate(
        self,
        repository: RepositorySettings,
        pull_request_number: int,
        *,
        should_require_merge_commit: bool = True,
    ) -> PullRequestCandidate:
        """Read one pull request.

        Args:
            repository: Repository to query.

        Returns:
            Pull request metadata.
        """
        endpoint = PULL_ENDPOINT_TEMPLATE.format(
            repository=repository.slug,
            pull_number=pull_request_number,
        )
        candidate = parse_candidate(
            repository.slug,
            self.get_json(endpoint),
            should_require_merge_commit=should_require_merge_commit,
        )
        if should_require_merge_commit:
            return candidate
        return replace_candidate_base_sha(candidate, repository, self.get_json)

    def get_commit_parents(
        self, repository: RepositorySettings, commit_sha: str
    ) -> tuple[str, ...]:
        """Read commit parent SHAs.

        Args:
            repository: Repository to query.

        Returns:
            Parent commit SHAs.

        Raises:
            GitHubError: If GitHub data is invalid.
        """
        endpoint = COMMIT_ENDPOINT_TEMPLATE.format(
            repository=repository.slug,
            commit_sha=commit_sha,
        )
        commit_mapping = require_mapping(self.get_json(endpoint), "commit")
        raw_parents = commit_mapping.get(COMMIT_PARENTS_KEY)
        if not isinstance(raw_parents, list):
            raise GitHubError(GITHUB_SHAPE_ERROR_TEMPLATE.format(resource="commit"))
        return tuple(
            require_text(require_mapping(each_parent, "commit"), PULL_SHA_KEY, "commit")
            for each_parent in raw_parents
        )

    def post_status(
        self,
        repository: RepositorySettings,
        commit_sha: str,
        state: StatusState,
        context: str,
        description: str,
    ) -> None:
        """Post one advisory commit status.

        Args:
            commit_sha: Commit receiving the status.

        Raises:
            GitHubError: If GitHub rejects the request.
        """
        endpoint = STATUS_ENDPOINT_TEMPLATE.format(
            repository=repository.slug,
            commit_sha=commit_sha,
        )
        request_body = _build_status_body(state, context, description)
        request_json(
            self.requester,
            "POST",
            self.api_url + endpoint,
            authorized_headers(self.installation_token),
            request_body,
            HTTP_CREATED,
        )

    def add_label(
        self,
        repository: RepositorySettings,
        pull_request_number: int,
        label: str,
    ) -> None:
        """Add one label to a pull request.

        Args:
            label: Label to add.

        Raises:
            GitHubError: If GitHub rejects the request.
        """
        endpoint = ISSUE_LABELS_ENDPOINT_TEMPLATE.format(
            repository=repository.slug,
            pull_number=pull_request_number,
        )
        request_body = json.dumps({ISSUE_LABELS_KEY: [label]}).encode(UTF8_ENCODING)
        request_json(
            self.requester,
            "POST",
            self.api_url + endpoint,
            authorized_headers(self.installation_token),
            request_body,
            HTTP_OK,
        )

    def remove_label(
        self,
        repository: RepositorySettings,
        pull_request_number: int,
        label: str,
    ) -> None:
        """Remove one label from a pull request.

        Args:
            repository: Repository containing the pull request.
            pull_request_number: Pull request number.
            label: Label to remove.

        Raises:
            GitHubError: If GitHub rejects the request.
        """
        _remove_label_if_present(
            self.requester,
            self.api_url,
            repository,
            pull_request_number,
            label,
            authorized_headers(self.installation_token),
        )

    def get_json(self, endpoint: str) -> object:
        """Read one JSON resource.

        Args:
            endpoint: Repository API path.

        Returns:
            Decoded JSON payload.
        """
        return request_json(
            self.requester,
            "GET",
            self.api_url + endpoint,
            authorized_headers(self.installation_token),
            None,
            HTTP_OK,
        )


def authorized_headers(token: str) -> dict[str, str]:
    """Build headers for an installation token request.

    Args:
        token: Installation token.

    Returns:
        Request headers.
    """
    return {
        AUTHORIZATION_HEADER: BEARER_PREFIX + token,
        ACCEPT_HEADER: GITHUB_ACCEPT_TYPE,
        CONTENT_TYPE_HEADER: JSON_CONTENT_TYPE,
        API_VERSION_HEADER: GITHUB_API_VERSION,
    }


def _delete_label(
    requester: HttpRequester, url: str, all_headers: dict[str, str]
) -> None:
    reply = requester("DELETE", url, all_headers, None)
    if reply.status_code in (HTTP_OK, HTTP_NO_CONTENT):
        return
    raise GitHubError(
        GITHUB_REQUEST_ERROR_TEMPLATE.format(
            method="DELETE", url=url, status_code=reply.status_code
        )
    )


def _decode_json_reply(reply: HttpReply, url: str) -> object:
    try:
        return json.loads(reply.body.decode(UTF8_ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GitHubError(GITHUB_JSON_ERROR_TEMPLATE.format(url=url)) from error


def _raise_unexpected_status(method: str, url: str, status_code: int) -> None:
    raise GitHubError(
        GITHUB_REQUEST_ERROR_TEMPLATE.format(
            method=method, url=url, status_code=status_code
        )
    )


def request_json(
    requester: HttpRequester,
    method: str,
    url: str,
    all_headers: dict[str, str],
    body: bytes | None,
    expected_status: int,
) -> object:
    """Send a request and decode JSON.
    Args:
        requester: Request function.
        method: HTTP method.
        url: Request URL.
        all_headers: Headers.
        body: Optional body.
        expected_status: Required status.
    Returns:
        Decoded JSON payload.
    Raises:
        GitHubError: If status or JSON is invalid.
    """
    reply = requester(method, url, all_headers, body)
    if reply.status_code != expected_status:
        _raise_unexpected_status(method, url, reply.status_code)
    return _decode_json_reply(reply, url)
