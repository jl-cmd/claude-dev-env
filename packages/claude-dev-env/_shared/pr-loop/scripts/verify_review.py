"""Verify that exactly one bugteam audit review exists on a PR at the correct commit.

Run after auditors complete. Non-zero exit means the lead must post a fallback
issue comment.
"""

import argparse
import json
import sys
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).absolute().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).absolute().parent))

from config.review_posting_constants import (
    BUGTEAM_LOOP_HEADER_TEMPLATE,
    EXIT_DUPLICATE_REVIEW,
    EXIT_FETCH_FAILED,
    EXIT_NO_REVIEW,
    EXIT_OK,
    EXIT_WRONG_COMMIT,
    LOOP_AUDIT_HEADER_TEMPLATE,
    MISSING_STRING_FIELD,
    REVIEWS_PATH_TEMPLATE,
    STATUS_OK,
)
from gh_util import _positive_int, run_gh


def _build_reviews_api_path(owner: str, repo: str, pull_number: int) -> str:
    return REVIEWS_PATH_TEMPLATE.format(owner=owner, repo=repo, pull_number=pull_number)


def _build_expected_headers(loop_number: int) -> tuple[str, str]:
    loop_audit_header = LOOP_AUDIT_HEADER_TEMPLATE.format(loop_number=loop_number)
    bugteam_loop_header = BUGTEAM_LOOP_HEADER_TEMPLATE.format(loop_number=loop_number)
    return loop_audit_header, bugteam_loop_header


def _is_matching_review(
    review_body: str | None, all_expected_headers: tuple[str, str]
) -> bool:
    body = review_body or ""
    return any(body.startswith(each_header) for each_header in all_expected_headers)


def _coerce_optional_string(maybe_field: object) -> str | None:
    return maybe_field if isinstance(maybe_field, str) else None


def _coerce_string_with_default(maybe_field: object) -> str:
    if isinstance(maybe_field, str):
        return maybe_field
    if isinstance(maybe_field, int) and not isinstance(maybe_field, bool):
        return str(maybe_field)
    return MISSING_STRING_FIELD


def _parse_paginated_slurp_response(
    raw_stdout: str,
) -> list[dict[str, object]] | None:
    try:
        parsed_pages = json.loads(raw_stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_pages, list):
        return None
    flattened_items: list[dict[str, object]] = []
    for each_page in parsed_pages:
        if not isinstance(each_page, list):
            return None
        for each_item in each_page:
            if not isinstance(each_item, dict):
                return None
            flattened_items.append(each_item)
    return flattened_items


def verify_pr_review(
    owner: str,
    repo: str,
    pull_number: int,
    expected_commit_id: str,
    loop_number: int,
) -> int:
    all_command = [
        "gh",
        "api",
        _build_reviews_api_path(owner, repo, pull_number),
        "--paginate",
        "--slurp",
    ]

    gh_response = run_gh(all_command)
    if gh_response.returncode != 0:
        print("Failed to fetch reviews via gh command", file=sys.stderr)
        return EXIT_FETCH_FAILED

    all_reviews = _parse_paginated_slurp_response(gh_response.stdout)
    if all_reviews is None:
        print("Failed to parse paginated reviews response", file=sys.stderr)
        return EXIT_FETCH_FAILED

    all_expected_headers = _build_expected_headers(loop_number)
    all_matching_reviews = [
        each_review
        for each_review in all_reviews
        if _is_matching_review(
            _coerce_optional_string(each_review.get("body")), all_expected_headers
        )
    ]

    if not all_matching_reviews:
        print(
            f"No review found with matching loop header for loop {loop_number}",
            file=sys.stderr,
        )
        return EXIT_NO_REVIEW

    if len(all_matching_reviews) > 1:
        print(
            f"Found {len(all_matching_reviews)} matching reviews for loop {loop_number} across commits",
            file=sys.stderr,
        )
        return EXIT_DUPLICATE_REVIEW

    all_reviews_on_expected_commit = [
        each_review
        for each_review in all_matching_reviews
        if each_review.get("commit_id") == expected_commit_id
    ]

    if not all_reviews_on_expected_commit:
        all_stale_commits = {
            _coerce_string_with_default(each_review.get("commit_id"))
            for each_review in all_matching_reviews
        }
        print(
            f"Review(s) found on commit(s) {all_stale_commits}, expected {expected_commit_id}",
            file=sys.stderr,
        )
        return EXIT_WRONG_COMMIT

    found_review = all_reviews_on_expected_commit[0]
    review_id = _coerce_string_with_default(found_review.get("id"))
    review_url = _coerce_string_with_default(found_review.get("html_url"))
    confirmed_review = {
        "status": STATUS_OK,
        "review_id": review_id,
        "review_url": review_url,
    }
    print(json.dumps(confirmed_review))
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify exactly one bugteam audit review exists at the correct commit"
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=_positive_int)
    parser.add_argument("--commit-id", required=True, dest="commit_id")
    parser.add_argument("--loop", required=True, type=_positive_int)

    parsed_arguments = parser.parse_args()

    return verify_pr_review(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        pull_number=parsed_arguments.number,
        expected_commit_id=parsed_arguments.commit_id,
        loop_number=parsed_arguments.loop,
    )


if __name__ == "__main__":
    sys.exit(main())
