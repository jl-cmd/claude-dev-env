"""Check for bugbot CI check runs on a commit.

Usage:
  python scripts/check_bugbot_ci.py --owner <O> --repo <R> --sha <SHA>
  python scripts/check_bugbot_ci.py --owner <O> --repo <R> --sha <SHA> --check-active
  python scripts/check_bugbot_ci.py --owner <O> --repo <R> --sha <SHA> --check-clean

Default mode (no flag):
  0 — bugbot check run found (printed to stdout as JSON)
  1 — no bugbot check run found
  EXIT_CODE_GH_ERROR — gh CLI error

``--check-active`` mode:
  0 — bugbot check run is queued or in_progress
  1 — bugbot check run is absent or no longer active

``--check-clean`` mode (silent-pass detection):
  0 — bugbot check run is completed with success/neutral conclusion
  1 — bugbot check run is absent, still active, or completed with a
      non-clean conclusion (failure, action_required, etc.)
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
    ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS,
    BUGBOT_CHECK_RUN_COMPLETED_STATUS,
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


def _classify_bugbot_check_run(
    completed_process: subprocess.CompletedProcess[str],
) -> bool | None:
    """Classify the bugbot check run state from a gh API process result.

    Args:
        completed_process: Result of calling ``_run_check_runs_api``.

    Returns:
        True when the captured stdout contains a bugbot check run with a
        ``completed`` status and a conclusion in
        ``ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS``. False when no such
        check run is present (absent, still active, or completed with a
        non-clean conclusion). None when ``completed_process.returncode``
        is non-zero, signalling a gh CLI failure that the caller must
        surface separately from "not clean".
    """
    if completed_process.returncode != 0:
        return None
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
        if each_status != BUGBOT_CHECK_RUN_COMPLETED_STATUS:
            return False
        each_conclusion: object = check_entry.get("conclusion")
        return (
            isinstance(each_conclusion, str)
            and each_conclusion in ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS
        )
    return False


def is_bugbot_run_clean(*, owner: str, repo: str, sha: str) -> bool | None:
    """Check whether bugbot has a completed check run with a clean conclusion.

    A "silent pass" is bugbot's signal that it found no issues: the CI
    check run completes with a ``success`` or ``neutral`` conclusion and
    no review comment is posted. This function detects that signal so
    callers can treat it as equivalent to an explicit clean review.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        sha: Commit SHA to check.

    Returns:
        True when a bugbot check run is completed with a conclusion in
        ``ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS``. False when the
        check run is absent, still active, or completed with a non-clean
        conclusion. None when the gh CLI returns an error so the caller
        can distinguish a transient API failure from a "not clean"
        result.
    """
    completed_process = _run_check_runs_api(owner=owner, repo=repo, sha=sha)
    return _classify_bugbot_check_run(completed_process)


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with owner, repo, sha, and mode flags.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--sha", required=True, help="Commit SHA to check")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--check-active",
        action="store_true",
        default=False,
        help="Check for active (queued/in-progress) check runs only",
    )
    mode_group.add_argument(
        "--check-clean",
        action="store_true",
        default=False,
        help=(
            "Check for a completed bugbot check run with a "
            "success/neutral conclusion (silent-pass detection)"
        ),
    )
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point for check_bugbot_ci.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        Exit code per the mode-specific contract documented in the
        module docstring.
    """
    arguments = parse_arguments(all_arguments)
    if arguments.check_clean:
        completed_process = _run_check_runs_api(
            owner=arguments.owner,
            repo=arguments.repo,
            sha=arguments.sha,
        )
        if completed_process.returncode != 0:
            print(f"gh api error: {completed_process.stderr}", file=sys.stderr)
            return EXIT_CODE_GH_ERROR
        is_clean = _classify_bugbot_check_run(completed_process)
        if is_clean is not True:
            print("bugbot: not clean")
        return 0 if is_clean is True else 1
    if arguments.check_active:
        is_active = is_bugbot_run_active(
            owner=arguments.owner,
            repo=arguments.repo,
            sha=arguments.sha,
        )
        if not is_active:
            print("bugbot: not found")
        return 0 if is_active else 1
    return check_bugbot_ci(
        owner=arguments.owner,
        repo=arguments.repo,
        sha=arguments.sha,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
