"""Fetch GitHub Copilot reviews for a pull request, newest first.

Usage:
  python scripts/fetch_copilot_reviews.py --owner <O> --repo <R> --pr-number <N>

Output: JSON array of Copilot reviews to stdout, each with id, state, body,
commit_id, submitted_at, and html_url.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_pr_converge_dir = Path(__file__).resolve().parent.parent
if str(_pr_converge_dir) not in sys.path:
    sys.path.insert(0, str(_pr_converge_dir))

from config.constants import (
    COPILOT_LOGIN_FILTER_SUBSTRING,
    GH_REVIEWS_PATH_TEMPLATE,
    REVIEWS_PER_PAGE,
)


def fetch_copilot_reviews(
    *, owner: str, repo: str, number: int
) -> list[dict[str, object]]:
    """Return Copilot reviews for a PR, newest first.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        number: Pull request number.

    Returns:
        List of Copilot review entries sorted by submitted_at descending.

    Raises:
        SystemExit: When the gh CLI call fails.
    """
    endpoint_path = GH_REVIEWS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    completed_process = subprocess.run(
        [
            "gh", "api",
            f"{endpoint_path}?per_page={REVIEWS_PER_PAGE}",
            "--paginate", "--slurp",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed_process.returncode != 0:
        print(f"gh api error: {completed_process.stderr}", file=sys.stderr)
        raise SystemExit(1)
    raw_output: object = json.loads(completed_process.stdout)
    if not isinstance(raw_output, list):
        return []
    all_pages: list[list[dict[str, object]]] = [
        each_page for each_page in raw_output if isinstance(each_page, list)
    ]
    all_flat: list[dict[str, object]] = [
        each_item for each_page in all_pages for each_item in each_page
    ]
    copilot_reviews: list[dict[str, object]] = []
    for each_review in all_flat:
        user_object: object = each_review.get("user")
        if not isinstance(user_object, dict):
            continue
        raw_login: object = user_object.get("login")
        if not isinstance(raw_login, str):
            continue
        if COPILOT_LOGIN_FILTER_SUBSTRING not in raw_login.lower():
            continue
        copilot_reviews.append({
            "id": each_review.get("id"),
            "state": each_review.get("state"),
            "body": each_review.get("body"),
            "commit_id": each_review.get("commit_id"),
            "submitted_at": each_review.get("submitted_at"),
            "html_url": each_review.get("html_url"),
        })
    copilot_reviews.sort(
        key=lambda each_review: str(each_review.get("submitted_at", "")),
        reverse=True,
    )
    return copilot_reviews


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with owner, repo, and number.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--pr-number", required=True, type=int, help="Pull request number")
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point for fetch_copilot_reviews.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        0 on success, 1 on error.
    """
    arguments = parse_arguments(all_arguments)
    all_reviews = fetch_copilot_reviews(
        owner=arguments.owner,
        repo=arguments.repo,
        number=getattr(arguments, "pr_number"),
    )
    json.dump(all_reviews, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))