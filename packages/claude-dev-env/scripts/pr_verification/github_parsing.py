from __future__ import annotations

from collections.abc import Mapping

from .config.constants import (
    GITHUB_SHAPE_ERROR_TEMPLATE,
    PULL_BASE_KEY,
    PULL_DRAFT_KEY,
    PULL_HEAD_KEY,
    PULL_LIST_RESOURCE_NAME,
    PULL_MERGE_SHA_KEY,
    PULL_NUMBER_KEY,
    PULL_REF_KEY,
    PULL_RESOURCE_NAME,
    PULL_SHA_KEY,
)
from .model import PullRequestCandidate


class GitHubError(RuntimeError):
    """Raised when GitHub metadata has an invalid shape."""


def _require_pull_list(all_pull_entries: object) -> list[object]:
    if isinstance(all_pull_entries, list):
        return all_pull_entries
    raise GitHubError(
        GITHUB_SHAPE_ERROR_TEMPLATE.format(resource=PULL_LIST_RESOURCE_NAME)
    )


def _parse_pull_candidates(
    repository_slug: str,
    all_pull_entries: list[object],
    should_require_merge_commit: bool,
) -> tuple[PullRequestCandidate, ...]:
    all_candidates: list[PullRequestCandidate] = []
    for each_pull in all_pull_entries:
        maybe_candidate = parse_recognized_candidate(
            repository_slug,
            each_pull,
            should_require_merge_commit=should_require_merge_commit,
        )
        if maybe_candidate is not None:
            all_candidates.append(maybe_candidate)
    return tuple(all_candidates)


def _read_pull_branches(
    all_pull_fields: Mapping[str, object],
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    base = require_mapping(all_pull_fields.get(PULL_BASE_KEY), PULL_RESOURCE_NAME)
    head = require_mapping(all_pull_fields.get(PULL_HEAD_KEY), PULL_RESOURCE_NAME)
    return base, head


def _read_pull_draft(all_pull_fields: Mapping[str, object]) -> bool:
    is_draft = all_pull_fields.get(PULL_DRAFT_KEY)
    if isinstance(is_draft, bool):
        return is_draft
    raise GitHubError(GITHUB_SHAPE_ERROR_TEMPLATE.format(resource=PULL_RESOURCE_NAME))


def parse_candidate(
    repository_slug: str,
    raw_pull: object,
    *,
    should_require_merge_commit: bool,
) -> PullRequestCandidate:
    """Parse pull request metadata.

    Args:
        repository_slug: Repository slug.
        raw_pull: GitHub pull JSON.

    Returns:
        Parsed pull request.

    Raises:
        GitHubError: If metadata is invalid.
    """
    pull = require_mapping(raw_pull, PULL_RESOURCE_NAME)
    base, head = _read_pull_branches(pull)
    pull_number = require_positive_integer(pull, PULL_NUMBER_KEY, PULL_RESOURCE_NAME)
    return PullRequestCandidate(
        repository_slug=repository_slug,
        pull_request_number=pull_number,
        base_ref=require_text(base, PULL_REF_KEY, PULL_RESOURCE_NAME),
        base_sha=require_text(base, PULL_SHA_KEY, PULL_RESOURCE_NAME),
        head_sha=require_text(head, PULL_SHA_KEY, PULL_RESOURCE_NAME),
        merge_sha=_read_merge_sha(pull, should_require_merge_commit),
        is_draft=_read_pull_draft(pull),
    )


def _read_merge_sha(
    all_pull_fields: Mapping[str, object],
    should_require_merge_commit: bool,
) -> str:
    merge_sha = all_pull_fields.get(PULL_MERGE_SHA_KEY)
    if merge_sha is None and not should_require_merge_commit:
        return ""
    if not isinstance(merge_sha, str) or not merge_sha:
        raise GitHubError(
            GITHUB_SHAPE_ERROR_TEMPLATE.format(resource=PULL_RESOURCE_NAME)
        )
    return merge_sha


def parse_recognized_candidate(
    repository_slug: str,
    raw_pull: object,
    *,
    should_require_merge_commit: bool = True,
) -> PullRequestCandidate | None:
    """Parse a pull request with a merge commit.

    Args:
        repository_slug: Repository slug.
        raw_pull: GitHub pull JSON.

    Returns:
        Parsed pull request or None.
    """
    pull = require_mapping(raw_pull, PULL_RESOURCE_NAME)
    if not should_require_merge_commit:
        return parse_candidate(
            repository_slug,
            pull,
            should_require_merge_commit=False,
        )
    if pull.get(PULL_MERGE_SHA_KEY) is None:
        return None
    return parse_candidate(repository_slug, pull, should_require_merge_commit=True)


def require_mapping(raw_payload: object, resource: str) -> Mapping[str, object]:
    if not isinstance(raw_payload, Mapping):
        raise GitHubError(GITHUB_SHAPE_ERROR_TEMPLATE.format(resource=resource))
    return raw_payload


def require_text(
    all_payload_fields: Mapping[str, object], field_name: str, resource: str
) -> str:
    """Read required text from a JSON object.

    Args:
        all_payload_fields: JSON object.

    Returns:
        Required text.

    Raises:
        GitHubError: If the field is absent.
    """
    field_text = all_payload_fields.get(field_name)
    if not isinstance(field_text, str) or not field_text:
        raise GitHubError(GITHUB_SHAPE_ERROR_TEMPLATE.format(resource=resource))
    return field_text


def require_positive_integer(
    all_payload_fields: Mapping[str, object], field_name: str, resource: str
) -> int:
    """Read a required positive integer.

    Args:
        all_payload_fields: JSON object.

    Returns:
        Required integer.

    Raises:
        GitHubError: If the field is invalid.
    """
    field_integer = all_payload_fields.get(field_name)
    if isinstance(field_integer, bool) or not isinstance(field_integer, int):
        raise GitHubError(GITHUB_SHAPE_ERROR_TEMPLATE.format(resource=resource))
    if field_integer < 1:
        raise GitHubError(GITHUB_SHAPE_ERROR_TEMPLATE.format(resource=resource))
    return field_integer
