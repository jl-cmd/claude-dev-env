"""CLI entrypoint that applies the five PR label axes: type, size, status, area, stacked.

::

    ok:   --dry-run          -> prints the label diff, calls no API
    ok:   (no --dry-run)     -> prints the diff, then applies it

Pure derivation lives in `pr_labeler_derivation.py`; the GitHub API transport
lives in `pr_labeler_transport.py`, both beside this module. This file only
parses arguments, wires the two together, and reports the result.
"""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

_repo_root_path = str(Path(__file__).resolve().parents[2])
if _repo_root_path not in sys.path:
    sys.path.insert(0, _repo_root_path)

from pr_labeler_derivation import LabelDiff, compute_label_diff, load_labeler_config
from pr_labeler_transport import (
    GitHubApiCaller,
    GitHubApiError,
    apply_label_diff,
    call_github_api,
    fetch_pull_request_snapshot,
)

from config.pr_labeler_constants import GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME


def format_label_diff_report(label_diff: LabelDiff, all_current_labels: frozenset[str]) -> str:
    """Render the current labels alongside what the diff would add and remove.

    Args:
        label_diff: The computed additions and removals.
        all_current_labels: Every label the pull request carries right now.

    Returns:
        A three-line report: current labels, labels to add, labels to remove.
    """
    return (
        f"current labels: {sorted(all_current_labels)}\n"
        f"labels to add: {sorted(label_diff.labels_to_add)}\n"
        f"labels to remove: {sorted(label_diff.labels_to_remove)}"
    )


def parse_command_line_arguments(all_argv: Sequence[str]) -> argparse.Namespace:
    """Parse the labeler's command-line flags.

    Args:
        all_argv: The argument vector, excluding the program name.

    Returns:
        The parsed namespace, carrying `repo`, `pr`, `config`, and `dry_run`.
    """
    argument_parser = argparse.ArgumentParser(
        description="Apply the five label axes to a pull request."
    )
    argument_parser.add_argument("--repo", required=True, help="owner/name of the repository")
    argument_parser.add_argument("--pr", required=True, type=int, help="pull request number")
    argument_parser.add_argument("--config", required=True, help="path to pr_labeler_config.yml")
    argument_parser.add_argument(
        "--dry-run", action="store_true", help="report the diff without calling the API"
    )
    return argument_parser.parse_args(all_argv)


def _emit_line(line_text: str, destination_stream: TextIO) -> None:
    destination_stream.write(line_text + "\n")


def main(
    all_argv: Sequence[str],
    call_api: GitHubApiCaller = call_github_api,
    report_stream: TextIO = sys.stdout,
    error_stream: TextIO = sys.stderr,
) -> int:
    """Apply the five label axes to one pull request.

    ::

        ok:   GITHUB_TOKEN set, --dry-run     -> prints the diff, returns 0
        flag: GITHUB_TOKEN unset               -> prints an error, returns 1
        flag: a GitHub API call fails          -> prints an error, returns 1

    Args:
        all_argv: The argument vector, excluding the program name.
        call_api: The GitHub API transport, overridable for tests.
        report_stream: Where the label-diff report is written, overridable for tests.
        error_stream: Where error messages are written, overridable for tests.

    Returns:
        0 on success (dry-run or applied), 1 when GITHUB_TOKEN is unset or a
        GitHub API call fails.
    """
    parsed_arguments = parse_command_line_arguments(all_argv)
    github_token = os.environ.get(GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME, "")
    if not github_token:
        _emit_line("::error::GITHUB_TOKEN environment variable is required", error_stream)
        return 1

    labeler_config = load_labeler_config(Path(parsed_arguments.config))
    try:
        pull_request_snapshot = fetch_pull_request_snapshot(
            parsed_arguments.repo, parsed_arguments.pr, github_token, call_api
        )
        label_diff = compute_label_diff(pull_request_snapshot, labeler_config)

        _emit_line(
            format_label_diff_report(label_diff, pull_request_snapshot.current_labels),
            report_stream,
        )

        if parsed_arguments.dry_run:
            return 0

        apply_label_diff(
            parsed_arguments.repo, parsed_arguments.pr, github_token, label_diff, call_api
        )
    except GitHubApiError as api_error:
        _emit_line(
            f"::error::GitHub API request failed with status {api_error.status_code}",
            error_stream,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
