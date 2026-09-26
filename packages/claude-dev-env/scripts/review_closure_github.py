"""Read from GitHub what the review closure verdict rests on.

Four reads answer one pull request: the pull request itself, its review
threads, its top-level comments, and the check runs on its head commit.

::

    read_pull_request("jl-cmd/claude-dev-env", 1442, token)
    read_review_threads("jl-cmd/claude-dev-env", 1442, token)
    read_top_level_comments("jl-cmd/claude-dev-env", 1442, token)
    read_approvals_conclusion("jl-cmd/claude-dev-env", "ab845eb", token)

Two routes carry the review threads. A Claude Code session reaches GitHub
through a proxy that refuses GraphQL and serves the threads over a REST route
of its own, so the REST route is read first and the GraphQL query answers for
a workflow runner.
"""

from __future__ import annotations

import functools
import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping

from dev_env_scripts_constants.review_closure_constants import (
    ALL_THREAD_NODE_KEYS,
    ALL_TOKEN_ENVIRONMENT_VARIABLES,
    CHECK_RUN_PAGE_SIZE,
    CHECK_RUNS_ENDPOINT_TEMPLATE,
    CHECK_RUNS_KEY,
    COMMENT_PAGE_SIZE,
    GET_METHOD,
    GITHUB_API_ROOT,
    GITHUB_GRAPHQL_ENDPOINT,
    MAX_COMMENT_PAGES,
    NAME_VARIABLE,
    NO_SIGN_IN_MESSAGE,
    NUMBER_VARIABLE,
    OWNER_VARIABLE,
    PAGE_SIZE_VARIABLE,
    POST_METHOD,
    PULL_REQUEST_ENDPOINT_TEMPLATE,
    QUERY_KEY,
    REQUEST_FAILED_TEMPLATE,
    REQUEST_TIMEOUT_SECONDS,
    REVIEW_COMMENTS_ENDPOINT_TEMPLATE,
    REVIEW_THREAD_PAGE_SIZE,
    REVIEW_THREAD_QUERY,
    REVIEW_THREADS_ENDPOINT_TEMPLATE,
    SLUG_SEPARATOR,
    TOP_LEVEL_COMMENTS_ENDPOINT_TEMPLATE,
    UNREADABLE_TOP_LEVEL_COMMENT_TEMPLATE,
    VARIABLES_KEY,
)
from pr_verification.config.constants import (
    ACCEPT_HEADER,
    API_VERSION_HEADER,
    AUTHORIZATION_HEADER,
    BEARER_PREFIX,
    CONTENT_TYPE_HEADER,
    GITHUB_ACCEPT_TYPE,
    GITHUB_API_VERSION,
    HTTP_OK,
    JSON_CONTENT_TYPE,
    UTF8_ENCODING,
)
from pr_verification.github_parsing import GitHubError
from review_closure_model import (
    ReviewThread,
    TopLevelComment,
    approvals_conclusion,
    comment_records_by_id,
    parse_thread,
    parse_top_level_comment,
)


def github_token() -> str:
    """Find the GitHub token this run authenticates with.

    Returns:
        The first token the environment carries.

    Raises:
        GitHubError: No token is set.
    """
    for each_variable in ALL_TOKEN_ENVIRONMENT_VARIABLES:
        token = os.environ.get(each_variable)
        if token:
            return token
    raise GitHubError(NO_SIGN_IN_MESSAGE)


def request_json(
    method: str,
    url: str,
    token: str,
    all_payload_fields: Mapping[str, object] | None,
) -> object:
    """Send one GitHub request and read its JSON answer.

    Args:
        method: The HTTP method.
        url: The absolute request URL.
        token: The GitHub token the request authenticates with.
        all_payload_fields: The JSON body to send, or None for a read.

    Returns:
        The decoded answer.

    Raises:
        GitHubError: The request failed, or GitHub answered with a status
            other than success.
    """
    request = _built_request(method, url, token, all_payload_fields)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as reply:
            return _decoded_answer(url, reply.status, reply.read())
    except (urllib.error.URLError, OSError, ValueError) as failure:
        raise GitHubError(str(failure)) from failure


def read_pull_request(slug: str, number: int, token: str) -> Mapping[str, object]:
    """Read one pull request from the GitHub REST API.

    Args:
        slug: The repository as ``owner/name``.
        number: The pull request number.
        token: The GitHub token the request authenticates with.

    Returns:
        The pull request fields, carrying its number, its head commit, and
        the account that opened it.

    Raises:
        GitHubError: GitHub answered with something other than a pull
            request object.
    """
    document = request_json(
        GET_METHOD,
        PULL_REQUEST_ENDPOINT_TEMPLATE.format(
            api_root=GITHUB_API_ROOT, slug=slug, number=number
        ),
        token,
        None,
    )
    if not isinstance(document, Mapping):
        raise GitHubError(str(document))
    return document


def read_review_threads(slug: str, number: int, token: str) -> tuple[ReviewThread, ...]:
    """Read the review threads on a pull request.

    Args:
        slug: The repository as ``owner/name``.
        number: The pull request number.
        token: The GitHub token the request authenticates with.

    Returns:
        Every review thread on the pull request.

    Raises:
        GitHubError: Both routes failed, or the GraphQL answer carried no
            review threads.
    """
    all_records = _thread_records_over_rest(slug, number, token)
    all_comment_records_by_id: Mapping[object, Mapping[str, object]] = {}
    if all_records is None:
        all_records = _thread_records_over_graphql(slug, number, token)
    else:
        all_comment_records_by_id = read_review_comments_by_id(slug, number, token)
    return tuple(
        parse_thread(each_record, all_comment_records_by_id)
        for each_record in all_records
        if isinstance(each_record, Mapping)
    )


def read_review_comments_by_id(
    slug: str, number: int, token: str
) -> dict[object, Mapping[str, object]]:
    """Read every review comment on a pull request, keyed by identifier.

    Args:
        slug: The repository as ``owner/name``.
        number: The pull request number.
        token: The GitHub token the request authenticates with.

    Returns:
        Each review comment under its identifier.

    Raises:
        GitHubError: A page answered with something other than a list.
    """
    return comment_records_by_id(
        _all_listed_records(REVIEW_COMMENTS_ENDPOINT_TEMPLATE, slug, number, token)
    )


def read_top_level_comments(
    slug: str, number: int, token: str
) -> tuple[TopLevelComment, ...]:
    """Read every top-level comment on a pull request.

    Args:
        slug: The repository as ``owner/name``.
        number: The pull request number.
        token: The GitHub token the request authenticates with.

    Returns:
        Each comment posted on the pull request itself, outside any review
        thread.

    Raises:
        GitHubError: A page answered with something other than a list, or a
            comment carried a timestamp that does not parse.
    """
    all_records = _all_listed_records(
        TOP_LEVEL_COMMENTS_ENDPOINT_TEMPLATE, slug, number, token
    )
    return tuple(
        _parsed_top_level_comment(each_record)
        for each_record in all_records
        if isinstance(each_record, Mapping)
    )


def _parsed_top_level_comment(
    all_comment_fields: Mapping[str, object],
) -> TopLevelComment:
    try:
        return parse_top_level_comment(all_comment_fields)
    except ValueError as failure:
        raise GitHubError(
            UNREADABLE_TOP_LEVEL_COMMENT_TEMPLATE.format(record=all_comment_fields)
        ) from failure


def _all_listed_records(
    endpoint_template: str, slug: str, number: int, token: str
) -> list[object]:
    all_records: list[object] = []
    for each_page in range(1, MAX_COMMENT_PAGES + 1):
        page = _listing_page(endpoint_template, slug, number, token, each_page)
        all_records.extend(page)
        if len(page) < COMMENT_PAGE_SIZE:
            break
    return all_records


def _listing_page(
    endpoint_template: str, slug: str, number: int, token: str, page: int
) -> list[object]:
    document = request_json(
        GET_METHOD,
        endpoint_template.format(
            api_root=GITHUB_API_ROOT,
            slug=slug,
            number=number,
            page_size=COMMENT_PAGE_SIZE,
            page=page,
        ),
        token,
        None,
    )
    if not isinstance(document, list):
        raise GitHubError(str(document))
    return document


def read_approvals_conclusion(slug: str, sha: str, token: str) -> str | None:
    """Read what the Claude Approvals check reports on one commit.

    Args:
        slug: The repository as ``owner/name``.
        sha: The head commit.
        token: The GitHub token the request authenticates with.

    Returns:
        That check run's conclusion, or None where it does not run.

    Raises:
        GitHubError: GitHub answered with an unexpected shape.
    """
    document = request_json(
        GET_METHOD,
        CHECK_RUNS_ENDPOINT_TEMPLATE.format(
            api_root=GITHUB_API_ROOT,
            slug=slug,
            sha=sha,
            page_size=CHECK_RUN_PAGE_SIZE,
        ),
        token,
        None,
    )
    return approvals_conclusion(_check_run_records(document))


def _check_run_records(document: object) -> list[object]:
    if not isinstance(document, Mapping):
        raise GitHubError(str(document))
    all_check_runs = document.get(CHECK_RUNS_KEY)
    if not isinstance(all_check_runs, list):
        raise GitHubError(str(document))
    return all_check_runs


def _built_request(
    method: str,
    url: str,
    token: str,
    all_payload_fields: Mapping[str, object] | None,
) -> urllib.request.Request:
    return urllib.request.Request(
        url=url,
        data=_encoded_body(all_payload_fields),
        headers=_all_request_headers(token, all_payload_fields),
        method=method,
    )


def _all_request_headers(
    token: str, all_payload_fields: Mapping[str, object] | None
) -> dict[str, str]:
    all_headers = {
        ACCEPT_HEADER: GITHUB_ACCEPT_TYPE,
        API_VERSION_HEADER: GITHUB_API_VERSION,
        AUTHORIZATION_HEADER: BEARER_PREFIX + token,
    }
    if all_payload_fields is not None:
        all_headers[CONTENT_TYPE_HEADER] = JSON_CONTENT_TYPE
    return all_headers


def _encoded_body(all_payload_fields: Mapping[str, object] | None) -> bytes | None:
    if all_payload_fields is None:
        return None
    return json.dumps(all_payload_fields).encode(UTF8_ENCODING)


def _decoded_answer(url: str, status: int, body: bytes) -> object:
    if status != HTTP_OK:
        raise GitHubError(REQUEST_FAILED_TEMPLATE.format(url=url, status=status))
    return json.loads(body.decode(UTF8_ENCODING))


def _thread_records_over_rest(
    slug: str, number: int, token: str
) -> list[object] | None:
    try:
        document = request_json(
            GET_METHOD,
            REVIEW_THREADS_ENDPOINT_TEMPLATE.format(
                api_root=GITHUB_API_ROOT, slug=slug, number=number
            ),
            token,
            None,
        )
    except GitHubError:
        return None
    return document if isinstance(document, list) else None


def _thread_records_over_graphql(slug: str, number: int, token: str) -> list[object]:
    document = request_json(
        POST_METHOD,
        GITHUB_GRAPHQL_ENDPOINT,
        token,
        _thread_query_payload(slug, number),
    )
    all_records = functools.reduce(
        functools.partial(_field_at, document), ALL_THREAD_NODE_KEYS, document
    )
    if not isinstance(all_records, list):
        raise GitHubError(str(document))
    return all_records


def _thread_query_payload(slug: str, number: int) -> dict[str, object]:
    owner, _, name = slug.partition(SLUG_SEPARATOR)
    return {
        QUERY_KEY: REVIEW_THREAD_QUERY,
        VARIABLES_KEY: {
            OWNER_VARIABLE: owner,
            NAME_VARIABLE: name,
            NUMBER_VARIABLE: number,
            PAGE_SIZE_VARIABLE: REVIEW_THREAD_PAGE_SIZE,
        },
    }


def _field_at(document: object, all_fields: object, key: str) -> object:
    if not isinstance(all_fields, Mapping):
        raise GitHubError(str(document))
    return all_fields.get(key)
