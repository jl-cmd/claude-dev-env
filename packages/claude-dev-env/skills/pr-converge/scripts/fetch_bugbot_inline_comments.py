"""Fetch unaddressed Cursor Bugbot inline comments for the latest Bugbot review on a commit.

Uses ``fetch_bugbot_reviews`` to find the newest submitted Bugbot review whose ``commit_id`` matches the caller
``current_head``, then returns only ``cursor[bot]`` inline comments whose ``pull_request_review_id`` matches that
review. This avoids misclassifying a PR when Bugbot posts more than one review on the same SHA: older inline threads
stay anchored to the earlier review id even when they share the same commit id.

Wraps the gh CLI invocation required by the gh-paginate rule for the comments list:
``gh api`` on ``repos/{owner}/{repo}/pulls/{number}/comments`` with ``--paginate --slurp`` and external JSON handling.
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
    CURSOR_BOT_LOGIN,
    GH_INLINE_COMMENTS_PATH_TEMPLATE,
)
from fetch_bugbot_reviews import fetch_bugbot_reviews


def fetch_bugbot_inline_comments(
    *,
    owner: str,
    repo: str,
    number: int,
    current_head: str,
) -> list[dict[str, object]]:
    """Return cursor[bot] inline comments for the latest Bugbot review on ``current_head``.

    Each entry contains comment_id, commit_id, path, line, and body.
    """
    all_bugbot_reviews = fetch_bugbot_reviews(owner=owner, repo=repo, number=number)
    latest_bugbot_review_for_head = next(
        (
            each_review
            for each_review in all_bugbot_reviews
            if each_review.get("commit_id") == current_head
        ),
        None,
    )
    if latest_bugbot_review_for_head is None:
        return []
    target_pull_request_review_id = latest_bugbot_review_for_head["review_id"]
    comments_endpoint = GH_INLINE_COMMENTS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    gh_command: list[str] = [
        "gh",
        "api",
        comments_endpoint,
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
    all_flat_comments = [each_comment for each_page in pages for each_comment in each_page]
    return [
        {
            "comment_id": each_comment["id"],
            "commit_id": each_comment.get("commit_id"),
            "path": each_comment.get("path"),
            "line": each_comment.get("line"),
            "body": _body_of(each_comment),
        }
        for each_comment in all_flat_comments
        if _login_of(each_comment) == CURSOR_BOT_LOGIN
        and each_comment.get("commit_id") == current_head
        and each_comment.get("pull_request_review_id") == target_pull_request_review_id
    ]


def _login_of(field_by_key: dict[str, object]) -> str | None:
    user_field = field_by_key.get("user")
    if not isinstance(user_field, dict):
        return None
    login_field = user_field.get("login")
    if not isinstance(login_field, str):
        return None
    return login_field


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
    parser.add_argument("--commit", required=True, dest="current_head")
    parsed_arguments = parser.parse_args()
    all_comments = fetch_bugbot_inline_comments(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        number=parsed_arguments.number,
        current_head=parsed_arguments.current_head,
    )
    json.dump(all_comments, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
