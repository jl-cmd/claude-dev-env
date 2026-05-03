"""Fetch GitHub Copilot reviewer reviews newest-first, classified as dirty or clean.

Wraps the gh CLI invocation required by the gh-paginate rule:
``gh api '...?per_page=100' --paginate --slurp`` piped through external Python
JSON handling (instead of ``gh --jq``, which runs per-page and breaks cross-page
operations like sort/reverse - see GitHub CLI #10459).

Classification follows the review's ``state`` field:
- ``APPROVED``                 -> ``"clean"``
- ``CHANGES_REQUESTED``        -> ``"dirty"``
- ``COMMENTED`` with non-empty body -> ``"dirty"`` (Copilot uses COMMENTED + body
  to flag findings without a hard block)
- everything else              -> ``"clean"`` (no actionable findings on PR)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import (
    ALL_COPILOT_DIRTY_REVIEW_STATES,
    COPILOT_CLEAN_REVIEW_STATE,
    COPILOT_REVIEWER_LOGIN,
    COPILOT_SOFT_DIRTY_REVIEW_STATE,
    GH_REVIEWS_PATH_TEMPLATE,
)
from review_field_helpers import body_of, login_of, state_of, submitted_at_of


def fetch_copilot_reviews(
    *,
    owner: str,
    repo: str,
    number: int,
) -> list[dict[str, object]]:
    """Return Copilot reviews newest-first, each with a clean/dirty classification.

    Each entry contains review_id, commit_id, submitted_at, state, body, and classification.
    """
    reviews_endpoint = GH_REVIEWS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    gh_command: list[str] = [
        "gh",
        "api",
        reviews_endpoint,
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
    all_flat_reviews = [each_review for each_page in pages for each_review in each_page]
    all_copilot_reviews = [
        each_review
        for each_review in all_flat_reviews
        if login_of(each_review) == COPILOT_REVIEWER_LOGIN
        and each_review.get("submitted_at") is not None
        and each_review.get("id") is not None
    ]
    all_copilot_reviews.sort(
        key=lambda each_review: submitted_at_of(each_review), reverse=True
    )
    return [
        {
            "review_id": each_review["id"],
            "commit_id": each_review.get("commit_id"),
            "submitted_at": each_review["submitted_at"],
            "state": state_of(each_review),
            "body": body_of(each_review),
            "classification": _classify_review(each_review),
        }
        for each_review in all_copilot_reviews
    ]


def _classify_review(field_by_key: dict[str, object]) -> str:
    review_state = state_of(field_by_key)
    if review_state == COPILOT_CLEAN_REVIEW_STATE:
        return "clean"
    if review_state not in ALL_COPILOT_DIRTY_REVIEW_STATES:
        return "clean"
    state_requires_body = review_state == COPILOT_SOFT_DIRTY_REVIEW_STATE
    if state_requires_body and not body_of(field_by_key):
        return "clean"
    return "dirty"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    all_reviews = fetch_copilot_reviews(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        number=parsed_arguments.number,
    )
    json.dump(all_reviews, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
