"""Request a Copilot review on the current PR via the requested_reviewers API.

The reviewer ID literal is ``copilot-pull-request-reviewer[bot]`` - the
``[bot]`` suffix is load-bearing per ``skills/copilot-review/SKILL.md``;
``Copilot``, ``copilot``, and ``github-copilot`` all silently no-op on this
endpoint. After this POST returns, GitHub schedules Copilot to render a review
on the current HEAD; the caller polls ``fetch_copilot_reviews.py`` to converge.
"""

import argparse
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evict_cached_config_modules import evict_cached_config_modules

evict_cached_config_modules()

from config.pr_converge_constants import (
    COPILOT_REVIEWER_REQUEST_ID,
    GH_REQUESTED_REVIEWERS_FIELD_TEMPLATE,
    GH_REQUESTED_REVIEWERS_PATH_TEMPLATE,
)


def request_copilot_review(*, owner: str, repo: str, number: int) -> None:
    """POST a Copilot review request to the PR's requested_reviewers endpoint."""
    requested_reviewers_endpoint = GH_REQUESTED_REVIEWERS_PATH_TEMPLATE.format(
        owner=owner, repo=repo, number=number
    )
    reviewer_field_value = GH_REQUESTED_REVIEWERS_FIELD_TEMPLATE.format(
        reviewer_id=COPILOT_REVIEWER_REQUEST_ID
    )
    gh_command: list[str] = [
        "gh",
        "api",
        "-X",
        "POST",
        requested_reviewers_endpoint,
        "-f",
        reviewer_field_value,
    ]
    subprocess.run(
        gh_command,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parsed_arguments = parser.parse_args()
    request_copilot_review(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        number=parsed_arguments.number,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
