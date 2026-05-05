"""Shared fetch primitives for PR reviewer bots (Bugbot, Copilot, Claude).

The reviewer-specific scripts (``fetch_bugbot_reviews.py``,
``fetch_copilot_reviews.py``, ``fetch_claude_reviews.py`` and their
inline-comment counterparts) are thin entry points that pass a ``ReviewerSpec``
to these functions. The spec carries the substring used to recognise the
reviewer's GitHub login (case-insensitive substring match - required because
some bots emit different login strings at the review-level vs inline-comment
endpoints) and the per-reviewer classify callable.

Wraps the gh CLI invocations required by the gh-paginate rule:
``gh api '...?per_page=100' --paginate --slurp`` piped through external Python
JSON handling (instead of ``gh --jq``, which runs per-page and breaks
cross-page operations like sort/reverse - see GitHub CLI issue 10459).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import (
    GH_INLINE_COMMENTS_PATH_TEMPLATE,
    GH_REVIEWS_PATH_TEMPLATE,
)
from review_field_helpers import body_of, login_of, state_of, submitted_at_of
from reviewer_specs import ReviewerSpec


def _login_matches_substring(
    field_by_key: dict[str, object], login_filter_substring: str
) -> bool:
    author_login = login_of(field_by_key) or ""
    return login_filter_substring.lower() in author_login.lower()


def _run_gh_paginated(*, endpoint_path: str) -> list[dict[str, object]]:
    gh_command: list[str] = [
        "gh",
        "api",
        endpoint_path,
        "--paginate",
        "--slurp",
    ]
    completed = subprocess.run(
        gh_command,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    pages: list[list[dict[str, object]]] = json.loads(completed.stdout)
    return [each_entry for each_page in pages for each_entry in each_page]


def fetch_reviewer_reviews(
    spec: ReviewerSpec,
    *,
    owner: str,
    repo: str,
    number: int,
) -> list[dict[str, object]]:
    """Return reviews from the matching reviewer newest-first, with classification.

    Each entry contains ``review_id``, ``commit_id``, ``submitted_at``,
    ``state``, ``body``, and ``classification`` (``"clean"`` or ``"dirty"``).
    Entries whose payload is missing ``submitted_at`` or ``id`` are dropped.
    """
    reviews_endpoint = GH_REVIEWS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    all_flat_reviews = _run_gh_paginated(endpoint_path=reviews_endpoint)
    all_matching_reviews = [
        each_review
        for each_review in all_flat_reviews
        if _login_matches_substring(each_review, spec.login_filter_substring)
        and each_review.get("submitted_at") is not None
        and each_review.get("id") is not None
    ]
    all_matching_reviews.sort(
        key=lambda each_review: submitted_at_of(each_review), reverse=True
    )
    return [
        {
            "review_id": each_review["id"],
            "commit_id": each_review.get("commit_id"),
            "submitted_at": each_review["submitted_at"],
            "state": state_of(each_review),
            "body": body_of(each_review),
            "classification": spec.classify_review(each_review),
        }
        for each_review in all_matching_reviews
    ]


def fetch_reviewer_inline_comments(
    spec: ReviewerSpec,
    *,
    owner: str,
    repo: str,
    number: int,
    current_head: str,
    all_reviews: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Return inline comments anchored to the latest matching review on ``current_head``.

    The ``all_reviews`` list is supplied by the caller (not fetched internally)
    so the entry-point scripts retain a patchable seam: tests that patch
    ``fetch_X_reviews`` on the entry-point module continue to work because the
    entry-point is what calls the reviews fetch.

    Each entry contains ``comment_id``, ``commit_id``, ``path``, ``line``, and
    ``body``. Returns an empty list when no review in ``all_reviews`` is
    anchored to ``current_head``.
    """
    latest_review_for_head = next(
        (
            each_review
            for each_review in all_reviews
            if each_review.get("commit_id") == current_head
        ),
        None,
    )
    if latest_review_for_head is None:
        return []
    target_pull_request_review_id = latest_review_for_head["review_id"]
    comments_endpoint = GH_INLINE_COMMENTS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    all_flat_comments = _run_gh_paginated(endpoint_path=comments_endpoint)
    return [
        {
            "comment_id": each_comment["id"],
            "commit_id": each_comment.get("commit_id"),
            "path": each_comment.get("path"),
            "line": each_comment.get("line"),
            "body": body_of(each_comment),
        }
        for each_comment in all_flat_comments
        if _login_matches_substring(each_comment, spec.login_filter_substring)
        and each_comment.get("commit_id") == current_head
        and each_comment.get("pull_request_review_id") == target_pull_request_review_id
    ]
