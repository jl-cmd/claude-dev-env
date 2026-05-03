"""Fetch Cursor Bugbot reviews newest-first, classified as dirty or clean.

Wraps the gh CLI invocation required by the gh-paginate rule:
`gh api '...?per_page=100' --paginate --slurp` piped through external Python
JSON handling (instead of `gh --jq`, which runs per-page and breaks cross-page
operations like sort/reverse — see GitHub CLI #10459).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import (
    BUGBOT_DIRTY_BODY_REGEX,
    CURSOR_BOT_LOGIN,
    GH_REVIEWS_PATH_TEMPLATE,
)


def fetch_bugbot_reviews(
    *,
    owner: str,
    repo: str,
    number: int,
) -> list[dict[str, object]]:
    """Return Cursor Bugbot reviews newest-first, each with a clean/dirty classification.

    Each entry contains review_id, commit_id, submitted_at, body, and classification.
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
    all_bugbot_reviews = [
        each_review
        for each_review in all_flat_reviews
        if _login_of(each_review) == CURSOR_BOT_LOGIN
        and each_review.get("submitted_at") is not None
        and each_review.get("id") is not None
    ]
    all_bugbot_reviews.sort(
        key=lambda each_review: _submitted_at_of(each_review), reverse=True
    )
    dirty_pattern = re.compile(BUGBOT_DIRTY_BODY_REGEX)
    return [
        {
            "review_id": each_review["id"],
            "commit_id": each_review.get("commit_id"),
            "submitted_at": each_review["submitted_at"],
            "body": _body_of(each_review),
            "classification": (
                "dirty"
                if dirty_pattern.search(_body_of(each_review))
                else "clean"
            ),
        }
        for each_review in all_bugbot_reviews
    ]


def _login_of(field_by_key: dict[str, object]) -> str | None:
    user_field = field_by_key.get("user")
    if not isinstance(user_field, dict):
        return None
    login_field = user_field.get("login")
    if not isinstance(login_field, str):
        return None
    return login_field


def _submitted_at_of(field_by_key: dict[str, object]) -> str:
    submitted_at_field = field_by_key.get("submitted_at")
    if not isinstance(submitted_at_field, str):
        return ""
    return submitted_at_field


def _body_of(field_by_key: dict[str, object]) -> str:
    body_field = field_by_key.get("body")
    if not isinstance(body_field, str):
        return ""
    return body_field


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    all_reviews = fetch_bugbot_reviews(
        owner=parsed_arguments.owner, repo=parsed_arguments.repo, number=parsed_arguments.number
    )
    json.dump(all_reviews, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
