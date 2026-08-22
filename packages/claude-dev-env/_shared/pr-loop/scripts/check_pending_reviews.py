"""Check for pending pull request reviews.

Usage:
  python scripts/check_pending_reviews.py --owner <O> --repo <R> --pr-number <N> [--user <substring>]

Exit codes:
  0 — pending review(s) found (printed to stdout as JSON array)
  1 — no pending reviews found
  EXIT_CODE_GH_ERROR — gh CLI error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_pr_converge_dir = Path(__file__).absolute().parent.parent
if str(_pr_converge_dir) not in sys.path:
    sys.path.insert(0, str(_pr_converge_dir))

from pr_converge_skill_constants.constants import (
    EXIT_CODE_GH_ERROR,
    GH_REVIEWS_PATH_TEMPLATE,
    REVIEWS_PER_PAGE,
)


def fetch_pending_reviews(
    *, owner: str, repo: str, number: int, user_filter: str | None = None
) -> list[dict[str, object]]:
    """Fetch pending reviews for a pull request.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        number: Pull request number.
        user_filter: Optional case-insensitive substring to match against user login.

    Returns:
        List of pending review entries.

    Raises:
        SystemExit: When the gh CLI call fails.
    """
    endpoint_path = (
        GH_REVIEWS_PATH_TEMPLATE.format(owner=owner, repo=repo, number=number)
        + f"?per_page={REVIEWS_PER_PAGE}"
    )
    completed_process = subprocess.run(
        ["gh", "api", endpoint_path, "--paginate", "--slurp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed_process.returncode != 0:
        print(f"gh api error: {completed_process.stderr}", file=sys.stderr)
        raise SystemExit(EXIT_CODE_GH_ERROR)
    raw_output: object = json.loads(completed_process.stdout)
    if not isinstance(raw_output, list):
        return []
    all_pages: list[list[dict[str, object]]] = [
        each_page for each_page in raw_output if isinstance(each_page, list)
    ]
    all_flat: list[dict[str, object]] = [
        each_item for each_page in all_pages for each_item in each_page
    ]
    pending_reviews: list[dict[str, object]] = []
    for each_review in all_flat:
        if each_review.get("state") != "PENDING":
            continue
        user_object: object = each_review.get("user")
        user_login: str = ""
        if isinstance(user_object, dict):
            raw_login: object = user_object.get("login")
            if isinstance(raw_login, str):
                user_login = raw_login
        raw_submitted: object = each_review.get("submitted_at")
        submitted_at: str = ""
        if isinstance(raw_submitted, str):
            submitted_at = raw_submitted
        raw_commit: object = each_review.get("commit_id")
        commit_short: str = ""
        if isinstance(raw_commit, str):
            commit_short = raw_commit[:7]
        if user_filter is not None and user_filter.lower() not in user_login.lower():
            continue
        pending_reviews.append(
            {
                "user": user_login,
                "submitted_at": submitted_at,
                "commit_id": commit_short,
            }
        )
    return pending_reviews


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
    parser.add_argument(
        "--user",
        default=None,
        help="Optional case-insensitive substring filter for user login",
    )
    return parser.parse_args(all_argv)


def main(
    all_arguments: list[str], *, user_filter: str | None = None
) -> int:
    """Entry point for check_pending_reviews.

    Args:
        all_arguments: Command-line arguments.
        user_filter: Override for user filter (default: from CLI).

    Returns:
        0 when pending reviews are found, 1 when none, EXIT_CODE_GH_ERROR on error.
    """
    arguments = parse_arguments(all_arguments)
    if arguments.owner is None:
        return 1
    pending = fetch_pending_reviews(
        owner=arguments.owner,
        repo=arguments.repo,
        number=getattr(arguments, "pr_number"),
        user_filter=arguments.user if user_filter is None else user_filter,
    )
    if pending:
        json.dump(pending, sys.stdout)
        sys.stdout.write("\n")
        return 0
    return 1


if __name__ == "__main__":
    all_argv = sys.argv[1:]
    arguments = parse_arguments(all_argv)
    raise SystemExit(main(all_argv, user_filter=arguments.user))
