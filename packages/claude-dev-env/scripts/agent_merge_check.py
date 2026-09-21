#!/usr/bin/env python3
"""Report whether the agent driving a pull request may merge it now.

An agent that drives a pull request in this repository merges it once the
repository's own gate passes and no review thread is open. This command reads
that state from GitHub and prints one verdict line, so the decision rests on
the pull request's live state rather than on the agent's reading of it.

Usage::

    python3 agent_merge_check.py jl-cmd/claude-dev-env 1442
    -> MERGE jl-cmd/claude-dev-env#1442 ab845eb :: green, no open review
       thread, ready for the agent to merge

Exit status is 0 for MERGE, 1 for HOLD, and 2 when the state could not be
read.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence

from dev_env_scripts_constants.agent_merge_check_constants import (
    ACCEPT_HEADER,
    ALL_HOLD_REASONS_BY_STATE,
    ALL_OUTDATED_KEYS,
    ALL_RESOLVED_KEYS,
    ALL_THREAD_NODE_KEYS,
    ALL_TOKEN_ENVIRONMENT_VARIABLES,
    AUTHORIZATION_HEADER,
    BEARER_PREFIX,
    COMMAND_DESCRIPTION,
    CONTENT_TYPE_HEADER,
    DRAFT_HOLD_REASON,
    DRAFT_KEY,
    ERROR_EXIT_CODE,
    GITHUB_ACCEPT_TYPE,
    GITHUB_API_ROOT,
    GITHUB_GRAPHQL_ENDPOINT,
    HEAD_KEY,
    HOLD_EXIT_CODE,
    HOLD_VERDICT_LABEL,
    JSON_CONTENT_TYPE,
    MERGE_EXIT_CODE,
    MERGE_VERDICT_LABEL,
    MERGEABLE_STATE_CLEAN,
    MERGEABLE_STATE_KEY,
    NAME_VARIABLE,
    NO_SIGN_IN_MESSAGE,
    NUMBER_ARGUMENT_HELP,
    NUMBER_KEY,
    NUMBER_VARIABLE,
    OWNER_VARIABLE,
    PAGE_SIZE_VARIABLE,
    PULL_REQUEST_ENDPOINT_TEMPLATE,
    QUERY_KEY,
    READY_DETAIL,
    REQUEST_TIMEOUT_SECONDS,
    REVIEW_THREAD_PAGE_SIZE,
    REVIEW_THREADS_ENDPOINT_TEMPLATE,
    SHA_KEY,
    SHORT_SHA_LENGTH,
    SLUG_ARGUMENT_HELP,
    SLUG_SEPARATOR,
    UNKNOWN_STATE_HOLD_TEMPLATE,
    UNRESOLVED_THREAD_QUERY,
    UNRESOLVED_THREADS_HOLD_TEMPLATE,
    UTF8_ENCODING,
    VARIABLES_KEY,
    VERDICT_LINE_TEMPLATE,
)


class MergeCheckError(Exception):
    """Raised when the pull request state could not be read."""


def hold_reason(
    all_pull_request_fields: Mapping[str, object],
    unresolved_thread_count: int,
) -> str | None:
    """Return why this pull request stays open, or None when it may merge.

    Args:
        all_pull_request_fields: The pull request as the GitHub API reports
            it, carrying its draft flag and its merge state.
        unresolved_thread_count: How many review threads are open on it.

    Returns:
        The reason text for a draft, for a merge state other than clean, and
        for an open review thread. None when the pull request is ready for
        the agent that drives it to merge it.
    """
    if all_pull_request_fields.get(DRAFT_KEY):
        return DRAFT_HOLD_REASON
    merge_state = all_pull_request_fields.get(MERGEABLE_STATE_KEY)
    if merge_state != MERGEABLE_STATE_CLEAN:
        return ALL_HOLD_REASONS_BY_STATE.get(
            merge_state,
            UNKNOWN_STATE_HOLD_TEMPLATE.format(state=merge_state),
        )
    if unresolved_thread_count > 0:
        return UNRESOLVED_THREADS_HOLD_TEMPLATE.format(count=unresolved_thread_count)
    return None


def verdict_line(
    slug: str,
    all_pull_request_fields: Mapping[str, object],
    reason: str | None,
) -> str:
    """Build the one line this command prints for a pull request.

    Args:
        slug: The repository as ``owner/name``.
        all_pull_request_fields: The pull request the verdict describes.
        reason: The hold reason, or None for a pull request that may merge.

    Returns:
        A line naming the verdict, the pull request, its head commit, and
        either the hold reason or the ready detail.
    """
    all_head_fields = all_pull_request_fields.get(HEAD_KEY, {})
    head_sha = ""
    if isinstance(all_head_fields, Mapping):
        head_sha = str(all_head_fields.get(SHA_KEY, ""))[:SHORT_SHA_LENGTH]
    return VERDICT_LINE_TEMPLATE.format(
        label=HOLD_VERDICT_LABEL if reason else MERGE_VERDICT_LABEL,
        slug=slug,
        number=all_pull_request_fields.get(NUMBER_KEY),
        sha=head_sha,
        detail=reason or READY_DETAIL,
    )


def count_unresolved_threads(all_thread_records: Sequence[object]) -> int:
    """Count the review threads that still wait on an answer.

    Args:
        all_thread_records: The review threads GitHub reports for the pull
            request.

    Returns:
        How many of them are unresolved and still point at live code. An
        outdated thread names code the pull request has since replaced, so it
        holds nothing back.
    """
    return sum(
        1
        for each_thread in all_thread_records
        if isinstance(each_thread, Mapping)
        and not _any_flag(each_thread, ALL_RESOLVED_KEYS)
        and not _any_flag(each_thread, ALL_OUTDATED_KEYS)
    )


def _any_flag(all_thread_fields: Mapping[str, object], all_keys: Sequence[str]) -> bool:
    return any(all_thread_fields.get(each_key) for each_key in all_keys)


def _github_token() -> str:
    for each_variable in ALL_TOKEN_ENVIRONMENT_VARIABLES:
        token = os.environ.get(each_variable)
        if token:
            return token
    raise MergeCheckError(NO_SIGN_IN_MESSAGE)


def _request_json(
    url: str,
    token: str,
    all_payload_fields: Mapping[str, object] | None,
) -> object:
    request = urllib.request.Request(url)
    request.add_header(ACCEPT_HEADER, GITHUB_ACCEPT_TYPE)
    request.add_header(AUTHORIZATION_HEADER, BEARER_PREFIX + token)
    body = None
    if all_payload_fields is not None:
        request.add_header(CONTENT_TYPE_HEADER, JSON_CONTENT_TYPE)
        body = json.dumps(all_payload_fields).encode(UTF8_ENCODING)
    try:
        with urllib.request.urlopen(
            request,
            data=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as answer:
            return json.loads(answer.read().decode(UTF8_ENCODING))
    except (urllib.error.URLError, ValueError) as failure:
        raise MergeCheckError(str(failure)) from failure


def read_pull_request(slug: str, number: int, token: str) -> Mapping[str, object]:
    """Read one pull request from the GitHub REST API.

    Args:
        slug: The repository as ``owner/name``.
        number: The pull request number.
        token: The GitHub token the request authenticates with.

    Returns:
        The pull request fields, carrying its draft flag, its merge state,
        and its head commit.

    Raises:
        MergeCheckError: The API call failed, or answered with something
            other than a pull request object.
    """
    document = _request_json(
        PULL_REQUEST_ENDPOINT_TEMPLATE.format(
            api_root=GITHUB_API_ROOT,
            slug=slug,
            number=number,
        ),
        token,
        None,
    )
    if not isinstance(document, Mapping):
        raise MergeCheckError(str(document))
    return document


def read_unresolved_thread_count(slug: str, number: int, token: str) -> int:
    """Read how many review threads on a pull request stay open.

    Two routes carry the same fact. A Claude Code session reaches GitHub
    through a proxy that refuses GraphQL and serves the review threads over a
    REST route of its own, so this reads that route first and falls back to
    the GraphQL query every other caller has.

    Args:
        slug: The repository as ``owner/name``.
        number: The pull request number.
        token: The GitHub token the request authenticates with.

    Returns:
        The count of unresolved, current review threads.

    Raises:
        MergeCheckError: Both routes failed, or both answered with a shape
            that carries no review threads.
    """
    all_thread_records = _thread_records_over_rest(slug, number, token)
    if all_thread_records is None:
        return _read_unresolved_thread_count_over_graphql(slug, number, token)
    return count_unresolved_threads(all_thread_records)


def _thread_records_over_rest(
    slug: str,
    number: int,
    token: str,
) -> list[object] | None:
    try:
        document = _request_json(
            REVIEW_THREADS_ENDPOINT_TEMPLATE.format(
                api_root=GITHUB_API_ROOT,
                slug=slug,
                number=number,
            ),
            token,
            None,
        )
    except MergeCheckError:
        return None
    return document if isinstance(document, list) else None


def _thread_query_payload(owner: str, name: str, number: int) -> dict[str, object]:
    return {
        QUERY_KEY: UNRESOLVED_THREAD_QUERY,
        VARIABLES_KEY: {
            OWNER_VARIABLE: owner,
            NAME_VARIABLE: name,
            NUMBER_VARIABLE: number,
            PAGE_SIZE_VARIABLE: REVIEW_THREAD_PAGE_SIZE,
        },
    }


def _read_unresolved_thread_count_over_graphql(
    slug: str,
    number: int,
    token: str,
) -> int:
    owner, _, name = slug.partition(SLUG_SEPARATOR)
    document = _request_json(
        GITHUB_GRAPHQL_ENDPOINT,
        token,
        _thread_query_payload(owner, name, number),
    )
    all_thread_records = functools.reduce(
        functools.partial(_field_at, document),
        ALL_THREAD_NODE_KEYS,
        document,
    )
    if not isinstance(all_thread_records, Sequence):
        raise MergeCheckError(str(document))
    return count_unresolved_threads(all_thread_records)


def _field_at(document: object, all_fields: object, key: str) -> object:
    if not isinstance(all_fields, Mapping):
        raise MergeCheckError(str(document))
    return all_fields.get(key)


def main(all_arguments: Sequence[str]) -> int:
    """Print the merge verdict for one pull request.

    Args:
        all_arguments: The command line, without the program name.

    Returns:
        Zero when the pull request may merge, one when it holds, and two
        when its state could not be read.
    """
    parser = argparse.ArgumentParser(description=COMMAND_DESCRIPTION)
    parser.add_argument("slug", help=SLUG_ARGUMENT_HELP)
    parser.add_argument("number", type=int, help=NUMBER_ARGUMENT_HELP)
    parsed = parser.parse_args(all_arguments)
    try:
        token = _github_token()
        all_pull_request_fields = read_pull_request(parsed.slug, parsed.number, token)
        unresolved_thread_count = read_unresolved_thread_count(
            parsed.slug, parsed.number, token
        )
    except MergeCheckError as failure:
        print(failure, file=sys.stderr)
        return ERROR_EXIT_CODE
    reason = hold_reason(all_pull_request_fields, unresolved_thread_count)
    print(verdict_line(parsed.slug, all_pull_request_fields, reason))
    return HOLD_EXIT_CODE if reason else MERGE_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
