#!/usr/bin/env python3
"""Report whether every review finding on a pull request head is answered.

::

    python3 review_closure.py jl-cmd/claude-dev-env 1442
    CLOSED jl-cmd/claude-dev-env#1442 ab845eb :: every review finding on this
    commit is answered

A finding is a review thread, a top-level comment on the pull request, or a
blocking Claude Approvals row. It waits until the agent driving the pull
request replies to it or pushes the fix. Exit status is 0 for CLOSED, 1 for OPEN, and 2 when the pull
request state could not be read.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from dev_env_scripts_constants.review_closure_constants import (
    CLOSED_EXIT_CODE,
    COMMAND_DESCRIPTION,
    DRIVER_LOGIN_ARGUMENT_HELP,
    ERROR_EXIT_CODE,
    FINDING_LINE_TEMPLATE,
    NUMBER_ARGUMENT_HELP,
    OPEN_EXIT_CODE,
    SLUG_ARGUMENT_HELP,
)
from pr_verification.github_parsing import GitHubError
from review_closure_github import (
    github_token,
    read_approvals_conclusion,
    read_pull_request,
    read_review_threads,
    read_top_level_comments,
)
from review_closure_model import (
    OpenFinding,
    all_open_findings,
    driver_logins,
    head_sha,
    verdict_line,
)


@dataclass(frozen=True)
class ClosureReport:
    """What one run of this command found on a pull request."""

    verdict: str
    all_findings: tuple[OpenFinding, ...]


def build_parser() -> argparse.ArgumentParser:
    """Build the command line this script accepts.

    Returns:
        A parser taking a repository slug, a pull request number, and any
        number of extra driver logins.
    """
    parser = argparse.ArgumentParser(description=COMMAND_DESCRIPTION)
    parser.add_argument("slug", help=SLUG_ARGUMENT_HELP)
    parser.add_argument("number", type=int, help=NUMBER_ARGUMENT_HELP)
    parser.add_argument(
        "--driver-login",
        action="append",
        default=[],
        help=DRIVER_LOGIN_ARGUMENT_HELP,
    )
    return parser


def closure_report(
    slug: str, number: int, all_extra_logins: Sequence[str], token: str
) -> ClosureReport:
    """Read one pull request and judge the findings on its head.

    Args:
        slug: The repository as ``owner/name``.
        number: The pull request number.
        all_extra_logins: Logins that count as the driving agent beside the
            account that opened the pull request.
        token: The GitHub token the reads authenticate with.

    Returns:
        The verdict line and each finding that waits.

    Raises:
        GitHubError: The pull request state could not be read.
    """
    all_pull_request_fields = read_pull_request(slug, number, token)
    all_findings = all_open_findings(
        read_review_threads(slug, number, token),
        read_top_level_comments(slug, number, token),
        driver_logins(all_pull_request_fields, all_extra_logins),
        read_approvals_conclusion(slug, head_sha(all_pull_request_fields), token),
    )
    return ClosureReport(
        verdict=verdict_line(slug, all_pull_request_fields, all_findings),
        all_findings=all_findings,
    )


def main(all_arguments: Sequence[str]) -> int:
    """Print the review closure verdict for one pull request.

    Args:
        all_arguments: The command line, without the program name.

    Returns:
        Zero when every finding is answered, one when a finding waits, and
        two when the pull request state could not be read.
    """
    parsed = build_parser().parse_args(all_arguments)
    try:
        report = closure_report(
            parsed.slug, parsed.number, parsed.driver_login, github_token()
        )
    except GitHubError as failure:
        print(failure, file=sys.stderr)
        return ERROR_EXIT_CODE
    print(report.verdict)
    for each_finding in report.all_findings:
        print(
            FINDING_LINE_TEMPLATE.format(
                subject=each_finding.subject, reason=each_finding.reason
            )
        )
    return OPEN_EXIT_CODE if report.all_findings else CLOSED_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
