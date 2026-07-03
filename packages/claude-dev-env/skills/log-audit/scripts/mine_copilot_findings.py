"""Turn the defects reviewers keep catching into upstream skill-edit proposals.

Copilot and Bugbot flag the same kinds of defect over and over — an untyped
return here, a broad except there. Each catch is a defect that reached review
because nothing blocked it at write time. This script reads recent reviewer
comments, sorts them into defect classes, and for each class names a concrete
skill or rule edit that would block that class upstream. The proposals are for a
human to apply through review, not for the agent to commit on its own.

Usage:
    mine_copilot_findings.py --repo owner/name
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from log_audit_constants.mine_copilot_findings_constants import (  # noqa: E402
    ALL_REVIEWER_BOT_LOGINS,
    KEYWORDS_BY_DEFECT_CLASS,
    MAX_EXAMPLES_PER_CLUSTER,
    PROPOSAL_BY_DEFECT_CLASS,
    PULL_COMMENTS_ENDPOINT_TEMPLATE,
    RECENT_PULL_COUNT,
    RECENT_PULLS_ENDPOINT_TEMPLATE,
)


class GithubCommandError(RuntimeError):
    """Raised when a gh api call fails or returns output that is not JSON."""


@dataclass(frozen=True)
class ReviewerComment:
    """One review comment left by a reviewer bot.

    Attributes:
        pull_number: The pull request the comment was left on.
        author: The reviewer bot's login.
        body: The comment text.
    """

    pull_number: int
    author: str
    body: str


@dataclass(frozen=True)
class DefectCluster:
    """The reviewer comments that fall into one defect class.

    Attributes:
        defect_class: The class name the comments were sorted into.
        count: How many comments fell into the class.
        example_bodies: A capped sample of the comment bodies in the class.
    """

    defect_class: str
    count: int
    example_bodies: tuple[str, ...]


@dataclass(frozen=True)
class SkillProposal:
    """A proposed skill-definition edit that blocks one defect class upstream.

    Attributes:
        defect_class: The defect class the edit would block.
        proposal: The concrete edit to make.
    """

    defect_class: str
    proposal: str


def classify_defect(comment_body: str) -> str | None:
    """Sort a review comment into a defect class by its keywords.

    Args:
        comment_body: The review comment text.

    Returns:
        The first defect class whose keywords appear in the comment, or None
        when no class matches.
    """
    lowered_body = comment_body.lower()
    for each_defect_class, each_keywords in KEYWORDS_BY_DEFECT_CLASS.items():
        if any(each_keyword in lowered_body for each_keyword in each_keywords):
            return each_defect_class
    return None


def cluster_defects(all_comments: list[ReviewerComment]) -> list[DefectCluster]:
    """Group review comments by defect class and rank by how often each recurs.

    Args:
        all_comments: The reviewer comments to sort.

    Returns:
        One cluster per defect class present, most frequent first, each with a
        capped sample of its comment bodies.
    """
    bodies_by_class: dict[str, list[str]] = defaultdict(list)
    for each_comment in all_comments:
        defect_class = classify_defect(each_comment.body)
        if defect_class is None:
            continue
        bodies_by_class[defect_class].append(each_comment.body)
    clusters: list[DefectCluster] = []
    for each_defect_class, each_bodies in bodies_by_class.items():
        clusters.append(
            DefectCluster(
                defect_class=each_defect_class,
                count=len(each_bodies),
                example_bodies=tuple(each_bodies[:MAX_EXAMPLES_PER_CLUSTER]),
            )
        )
    return sorted(clusters, key=lambda cluster: cluster.count, reverse=True)


def proposal_for_defect_class(defect_class: str) -> SkillProposal:
    """Return the skill-edit proposal that blocks a defect class upstream.

    Args:
        defect_class: The defect class to propose an edit for.

    Returns:
        The proposal mapped to the class.
    """
    return SkillProposal(
        defect_class=defect_class, proposal=PROPOSAL_BY_DEFECT_CLASS[defect_class]
    )


def _pull_number_from_url(pull_request_url: str) -> int | None:
    """Read the trailing pull number from a GitHub pull-request URL."""
    last_segment = pull_request_url.rsplit("/", 1)[-1]
    try:
        return int(last_segment)
    except ValueError:
        return None


def _reviewer_comment_from_payload(payload: object) -> ReviewerComment | None:
    """Build a ReviewerComment from one gh comment payload, or None to skip it."""
    if not isinstance(payload, dict):
        return None
    user_field = payload.get("user")
    login = user_field.get("login") if isinstance(user_field, dict) else None
    body = payload.get("body")
    pull_request_url = payload.get("pull_request_url")
    if not isinstance(login, str) or login not in ALL_REVIEWER_BOT_LOGINS:
        return None
    if not isinstance(body, str) or not isinstance(pull_request_url, str):
        return None
    pull_number = _pull_number_from_url(pull_request_url)
    if pull_number is None:
        return None
    return ReviewerComment(pull_number=pull_number, author=login, body=body)


def _run_gh_json(endpoint: str) -> object:
    """Run one gh api call for an endpoint and return its parsed JSON payload."""
    try:
        completed_process = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as missing_gh_error:
        raise GithubCommandError(
            "gh command not found; install the GitHub CLI to mine reviewer comments"
        ) from missing_gh_error
    except subprocess.CalledProcessError as gh_failure_error:
        raise GithubCommandError(
            f"gh api {endpoint} failed: {gh_failure_error.stderr.strip()}"
        ) from gh_failure_error
    try:
        return json.loads(completed_process.stdout)
    except json.JSONDecodeError as decode_error:
        raise GithubCommandError(
            f"gh api {endpoint} returned output that is not JSON"
        ) from decode_error


def _fetch_recent_pull_numbers(repo: str, pull_count: int) -> list[int]:
    """Fetch the most recently updated pull numbers, capped at pull_count."""
    pulls_payload = _run_gh_json(
        RECENT_PULLS_ENDPOINT_TEMPLATE.format(repo=repo, pull_count=pull_count)
    )
    recent_pull_numbers: list[int] = []
    if isinstance(pulls_payload, list):
        for each_pull in pulls_payload:
            if isinstance(each_pull, dict):
                pull_number = each_pull.get("number")
                if isinstance(pull_number, int):
                    recent_pull_numbers.append(pull_number)
    return recent_pull_numbers


def _fetch_pull_comments(repo: str, pull_number: int) -> list[object]:
    """Fetch one pull request's review comments through gh."""
    comments_payload = _run_gh_json(
        PULL_COMMENTS_ENDPOINT_TEMPLATE.format(repo=repo, pull_number=pull_number)
    )
    if isinstance(comments_payload, list):
        return list(comments_payload)
    return []


def _fetch_reviewer_comments(repo: str) -> list[ReviewerComment]:
    """Fetch reviewer-bot comments from the repo's most recent pull requests."""
    recent_pull_numbers = _fetch_recent_pull_numbers(repo, RECENT_PULL_COUNT)
    reviewer_comments: list[ReviewerComment] = []
    for each_pull_number in recent_pull_numbers:
        for each_payload in _fetch_pull_comments(repo, each_pull_number):
            parsed_comment = _reviewer_comment_from_payload(each_payload)
            if parsed_comment is not None:
                reviewer_comments.append(parsed_comment)
    return reviewer_comments


def main() -> int:
    """Print one skill-edit proposal per recurring reviewer defect class.

    Returns:
        The process exit code; zero on success.
    """
    parser = argparse.ArgumentParser(
        description="Mine reviewer defect patterns into skill-edit proposals."
    )
    parser.add_argument("--repo", required=True)
    parsed_arguments = parser.parse_args()
    try:
        comments = _fetch_reviewer_comments(parsed_arguments.repo)
    except GithubCommandError as gh_error:
        print(str(gh_error), file=sys.stderr)
        return 1
    clusters = cluster_defects(comments)
    for each_cluster in clusters:
        proposal = proposal_for_defect_class(each_cluster.defect_class)
        print(f"{each_cluster.count}\t{each_cluster.defect_class}\t{proposal.proposal}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
