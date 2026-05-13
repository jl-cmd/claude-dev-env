"""Post a fix reply to a pull request comment thread or as a general PR comment.

Usage:
  # Reply to an inline comment thread
  python scripts/post_fix_reply.py --owner <O> --repo <R> --pr-number <N> \
      --body "Fixed in <sha>" --in-reply-to <COMMENT_ID>

    python scripts/post_fix_reply.py --owner <O> --repo <R> --pr-number <N> \
      --body "Your reply text"

Exit codes:
  0 — reply posted successfully
  1 — gh CLI error
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_pr_converge_dir = Path(__file__).resolve().parent.parent
if str(_pr_converge_dir) not in sys.path:
    sys.path.insert(0, str(_pr_converge_dir))

from config.constants import (
    EXIT_CODE_GH_ERROR,
    GH_INLINE_COMMENT_CREATE_PATH_TEMPLATE,
    GH_ISSUE_COMMENT_CREATE_PATH_TEMPLATE,
)


def post_inline_reply(
    *,
    owner: str,
    repo: str,
    number: int,
    body: str,
    in_reply_to: int,
) -> int:
    """Post a reply to an inline pull request comment thread.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        number: Pull request number.
        body: Reply body text.
        in_reply_to: The comment ID to reply to.

    Returns:
        0 on success, 1 on failure.
    """
    endpoint_path = GH_INLINE_COMMENT_CREATE_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    completed_process = subprocess.run(
        [
            "gh",
            "api",
            endpoint_path,
            "-f",
            f"body={body}",
            "-f",
            f"in_reply_to={in_reply_to}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed_process.returncode != 0:
        print(f"gh api error: {completed_process.stderr}", file=sys.stderr)
        return EXIT_CODE_GH_ERROR
    return 0


def post_pr_comment(
    *,
    owner: str,
    repo: str,
    number: int,
    body: str,
) -> int:
    """Post a general PR comment.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        number: Pull request number (issue_number for PR comments).
        body: Comment body text.

    Returns:
        0 on success, 1 on failure.
    """
    endpoint_path = GH_ISSUE_COMMENT_CREATE_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    completed_process = subprocess.run(
        [
            "gh",
            "api",
            endpoint_path,
            "-f",
            f"body={body}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed_process.returncode != 0:
        print(f"gh api error: {completed_process.stderr}", file=sys.stderr)
        return EXIT_CODE_GH_ERROR
    return 0


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with owner, repo, number, body, and in_reply_to.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--pr-number", required=True, type=int, help="Pull request number")
    parser.add_argument("--body", required=True, help="Reply body text")
    parser.add_argument(
        "--in-reply-to",
        type=int,
        default=None,
        help="Comment ID to reply to (omit for general PR comment)",
    )
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point for post_fix_reply.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        0 on success, 1 on error.
    """
    arguments = parse_arguments(all_arguments)
    if arguments.in_reply_to is not None:
        return post_inline_reply(
            owner=arguments.owner,
            repo=arguments.repo,
            number=getattr(arguments, "pr_number"),
            body=arguments.body,
            in_reply_to=arguments.in_reply_to,
        )
    return post_pr_comment(
        owner=arguments.owner,
        repo=arguments.repo,
        number=getattr(arguments, "pr_number"),
        body=arguments.body,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
