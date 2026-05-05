"""Fetch unaddressed Claude inline comments for the latest Claude review on a commit.

Thin wrapper around ``reviewer_fetch_core.fetch_reviewer_inline_comments``
parameterised by ``claude_spec``. The ``fetch_claude_reviews`` call lives here
(rather than inside the core) so tests can patch it on this module to exercise
the inline-comments fetch in isolation.

Wraps the gh CLI invocation required by the gh-paginate rule for the comments
list: ``gh api`` on ``repos/{owner}/{repo}/pulls/{number}/comments`` with
``--paginate --slurp`` and external JSON handling.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from fetch_claude_reviews import fetch_claude_reviews
from reviewer_fetch_core import fetch_reviewer_inline_comments
from reviewer_specs import claude_spec


def fetch_claude_inline_comments(
    *,
    owner: str,
    repo: str,
    number: int,
    current_head: str,
) -> list[dict[str, object]]:
    """Return Claude inline comments for the latest Claude review on ``current_head``."""
    all_claude_reviews = fetch_claude_reviews(owner=owner, repo=repo, number=number)
    return fetch_reviewer_inline_comments(
        claude_spec,
        owner=owner,
        repo=repo,
        number=number,
        current_head=current_head,
        all_reviews=all_claude_reviews,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parser.add_argument("--commit", required=True, dest="current_head")
    parsed_arguments = parser.parse_args()
    all_comments = fetch_claude_inline_comments(
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
