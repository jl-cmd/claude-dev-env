from __future__ import annotations

import urllib.parse
from collections.abc import Callable
from dataclasses import replace

from .config.constants import (
    GIT_BRANCH_REF_SAFE_CHARACTERS,
    GIT_BRANCH_REFERENCE_ENDPOINT_TEMPLATE,
    GIT_REFERENCE_OBJECT_KEY,
    GIT_REFERENCE_RESOURCE_NAME,
    PULL_SHA_KEY,
)
from .github_parsing import require_mapping, require_text
from .model import PullRequestCandidate, RepositorySettings

GetJson = Callable[[str], object]


def _read_branch_sha(
    repository: RepositorySettings,
    base_ref: str,
    get_json: GetJson,
) -> str:
    endpoint = GIT_BRANCH_REFERENCE_ENDPOINT_TEMPLATE.format(
        repository=repository.slug,
        base_ref=urllib.parse.quote(
            base_ref,
            safe=GIT_BRANCH_REF_SAFE_CHARACTERS,
        ),
    )
    reference = require_mapping(get_json(endpoint), GIT_REFERENCE_RESOURCE_NAME)
    target = require_mapping(
        reference.get(GIT_REFERENCE_OBJECT_KEY),
        GIT_REFERENCE_RESOURCE_NAME,
    )
    return require_text(target, PULL_SHA_KEY, GIT_REFERENCE_RESOURCE_NAME)


def replace_candidate_base_sha(
    candidate: PullRequestCandidate,
    repository: RepositorySettings,
    get_json: GetJson,
) -> PullRequestCandidate:
    """Replace one pull request base SHA with its current branch tip.

    Args:
        candidate: Pull request candidate from the pulls API.
        repository: Repository containing the target branch.
        get_json: Authenticated GitHub JSON reader.

    Returns:
        Candidate carrying the current target branch SHA.
    """
    current_base_sha = _read_branch_sha(repository, candidate.base_ref, get_json)
    return replace(candidate, base_sha=current_base_sha)


def replace_candidate_base_shas(
    all_candidates: tuple[PullRequestCandidate, ...],
    repository: RepositorySettings,
    get_json: GetJson,
) -> tuple[PullRequestCandidate, ...]:
    """Replace pull request base SHAs with current unique branch tips.

    Args:
        all_candidates: Pull request candidates from the pulls API.
        repository: Repository containing the target branches.
        get_json: Authenticated GitHub JSON reader.

    Returns:
        Candidates carrying current target branch SHAs.
    """
    base_sha_by_ref = _read_unique_branch_shas(
        all_candidates,
        repository,
        get_json,
    )
    return tuple(
        replace(
            each_candidate,
            base_sha=base_sha_by_ref[each_candidate.base_ref],
        )
        for each_candidate in all_candidates
    )


def _resolve_candidate_base_shas(
    all_candidates: list[PullRequestCandidate],
    repository: RepositorySettings,
    get_json: GetJson,
    should_require_merge_commit: bool,
) -> tuple[PullRequestCandidate, ...]:
    candidates = tuple(all_candidates)
    if should_require_merge_commit:
        return candidates
    return replace_candidate_base_shas(candidates, repository, get_json)


def _read_unique_branch_shas(
    all_candidates: tuple[PullRequestCandidate, ...],
    repository: RepositorySettings,
    get_json: GetJson,
) -> dict[str, str]:
    base_sha_by_ref: dict[str, str] = {}
    for each_candidate in all_candidates:
        if each_candidate.base_ref in base_sha_by_ref:
            continue
        base_sha_by_ref[each_candidate.base_ref] = _read_branch_sha(
            repository,
            each_candidate.base_ref,
            get_json,
        )
    return base_sha_by_ref
