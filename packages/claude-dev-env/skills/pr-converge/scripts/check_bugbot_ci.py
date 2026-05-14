"""Check for bugbot CI check runs on a commit.

Usage:
  python scripts/check_bugbot_ci.py --owner <O> --repo <R> --sha <SHA>

Exit codes:
  0 — bugbot check run found (printed to stdout as JSON)
  1 — no bugbot check run found
  EXIT_CODE_GH_ERROR — gh CLI error
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
    ALL_BUGBOT_CHECK_RUN_ACTIVE_STATUSES,
    BUGBOT_CHECK_RUN_NAME_SUBSTRING,
    CHECK_RUNS_PER_PAGE,
    EXIT_CODE_GH_ERROR,
    GH_CHECK_RUNS_PATH_TEMPLATE,
)


def _run_check_runs_api(
    *, owner: str, repo: str, sha: str
) -> subprocess.CompletedProcess[str]:
    endpoint_path = GH_CHECK_RUNS_PATH_TEMPLATE.format(owner=owner, repo=repo, sha=sha)
    jq_filter = ".check_runs[] | {name, status, conclusion}"
    return subprocess.run(
        [
            "gh",
            "api",
            f"{endpoint_path}?per_page={CHECK_RUNS_PER_PAGE}",
            "--jq",
            jq_filter,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def check_bugbot_ci(*, owner: str, repo: str, sha: str) -> int:
    """Check whether a bugbot CI check run exists on the given commit.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        sha: Commit SHA to check.

    Returns:
        0 when a bugbot check run is found, 1 when absent,
        EXIT_CODE_GH_ERROR on gh CLI error.
    """
    completed_process = _run_check_runs_api(owner=owner, repo=repo, sha=sha)
    if completed_process.returncode != 0:
        print(f"gh api error: {completed_process.stderr}", file=sys.stderr)
        return EXIT_CODE_GH_ERROR
    for each_line in completed_process.stdout.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        try:
            check_entry: dict[str, object] = json.loads(stripped_line)
        except json.JSONDecodeError:
            continue
        each_name: object = check_entry.get("name")
        if not isinstance(each_name, str):
            continue
        if BUGBOT_CHECK_RUN_NAME_SUBSTRING.lower() in each_name.lower():
            json.dump(check_entry, sys.stdout)
            sys.stdout.write("\n")
            return 0
    return 1


def is_bugbot_run_active(*, owner: str, repo: str, sha: str) -> bool:
    """Check whether bugbot has an active (queued/in-progress) check run.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        sha: Commit SHA to check.

    Returns:
        True when a bugbot check run with an active status exists.
    """
    completed_process = _run_check_runs_api(owner=owner, repo=repo, sha=sha)
    if completed_process.returncode != 0:
        return False
    for each_line in completed_process.stdout.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        try:
            check_entry: dict[str, object] = json.loads(stripped_line)
        except json.JSONDecodeError:
            continue
        each_name: object = check_entry.get("name")
        if not isinstance(each_name, str):
            continue
        if BUGBOT_CHECK_RUN_NAME_SUBSTRING.lower() not in each_name.lower():
            continue
        each_status: object = check_entry.get("status")
        if (
            isinstance(each_status, str)
            and each_status in ALL_BUGBOT_CHECK_RUN_ACTIVE_STATUSES
        ):
            return True
    return False


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with owner, repo, and sha.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--sha", required=True, help="Commit SHA to check")
    parser.add_argument(
        "--check-active",
        action="store_true",
        default=False,
        help="Check for active (queued/in-progress) check runs only",
    )
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point for check_bugbot_ci.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        0 when a bugbot check run is found, 1 when absent,
        EXIT_CODE_GH_ERROR on error.
    """
    arguments = parse_arguments(all_arguments)
    if arguments.check_active:
        found = is_bugbot_run_active(
            owner=arguments.owner,
            repo=arguments.repo,
            sha=arguments.sha,
        )
        if not found:
            print("bugbot: not found")
        return 0 if found else 1
    return check_bugbot_ci(
        owner=arguments.owner,
        repo=arguments.repo,
        sha=arguments.sha,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
