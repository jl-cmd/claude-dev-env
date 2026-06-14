"""Preflight guard for the working directory and worktree before a PR-convergence run.

Usage:
  python preflight_worktree.py --owner <O> --repo <R> --mode <strict|classify>

Modes:
  strict   — autoconverge: the working directory must be the PR's own repo so
             EnterWorktree can create and enter the branch worktree. Any other
             state aborts (exit 1).
  classify — pr-converge: emit the environment classification so the caller can
             route. same_repo and different_repo both succeed (exit 0); a
             re-rooted session (no git work tree, or no readable origin) aborts
             (exit 1).

Output (stdout):
  A line 'PREFLIGHT_OUTCOME=<same_repo|different_repo|re_rooted>', a
  human-readable summary, and, on abort, a recovery instruction.

Exit codes:
  0 — safe to continue for the given mode
  1 — abort (the caller must stop and recover)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from skills_pr_loop_constants.preflight_constants import (
    ABORT_DIFFERENT_REPO_STRICT_TEMPLATE,
    ABORT_RE_ROOTED_TEMPLATE,
    ABORT_WORKTREE_BROKEN_TEMPLATE,
    ALL_GIT_IS_INSIDE_WORK_TREE_ARGS,
    ALL_GIT_REMOTE_GET_URL_ARGS,
    ALL_GIT_WORKTREE_LIST_ARGS,
    ALL_PREFLIGHT_MODES,
    CWD_IDENTITY_UNKNOWN,
    EXIT_PREFLIGHT_ABORT,
    EXIT_PREFLIGHT_OK,
    GIT_DIRECTORY_FLAG,
    GIT_EXECUTABLE,
    GIT_INSIDE_WORK_TREE_TRUE,
    GIT_SUBPROCESS_TIMEOUT_SECONDS,
    MODE_ARG_FLAG,
    MODE_STRICT,
    OUTCOME_DIFFERENT_REPO,
    OUTCOME_MARKER_TEMPLATE,
    OUTCOME_RE_ROOTED,
    OUTCOME_SAME_REPO,
    OWNER_ARG_FLAG,
    PREFLIGHT_CLI_DESCRIPTION,
    REMOTE_URL_IDENTITY_PATTERN,
    REPO_ARG_FLAG,
    ROUTE_DIFFERENT_REPO_TEMPLATE,
    SUMMARY_DIFFERENT_REPO_TEMPLATE,
    SUMMARY_RE_ROOTED_TEMPLATE,
    SUMMARY_SAME_REPO_TEMPLATE,
)


@dataclass(frozen=True)
class RepoIdentity:
    """A GitHub repository identity parsed from a git remote URL.

    Attributes:
        owner: Repository owner (login or org), lower-cased for comparison.
        repo: Repository name, lower-cased for comparison.
    """

    owner: str
    repo: str


@dataclass(frozen=True)
class PreflightVerdict:
    """Classification of the working directory against a target PR repo.

    Attributes:
        outcome: One of OUTCOME_SAME_REPO, OUTCOME_DIFFERENT_REPO, or
            OUTCOME_RE_ROOTED.
        cwd_identity: Parsed identity of the working directory's origin, or
            None when there is no git work tree, no origin, or an unparseable
            origin URL.
        has_healthy_worktree_machinery: True when 'git worktree list' runs
            cleanly in the working directory.
    """

    outcome: str
    cwd_identity: RepoIdentity | None
    has_healthy_worktree_machinery: bool


def parse_repo_identity(remote_url: str) -> RepoIdentity | None:
    """Parse a GitHub owner/repo from a git remote URL.

    Accepts the https, git@ (scp-like), and ssh:// forms and drops a trailing
    '.git'. Comparison is case-insensitive, so the returned owner and repo are
    lower-cased.

    Args:
        remote_url: The remote URL from 'git remote get-url origin'.

    Returns:
        A RepoIdentity, or None when the URL is not a GitHub remote.
    """
    match = REMOTE_URL_IDENTITY_PATTERN.search(remote_url.strip())
    if match is None:
        return None
    return RepoIdentity(
        owner=match.group("owner").lower(),
        repo=match.group("repo").lower(),
    )


def _run_git(
    working_directory: Path, all_git_arguments: tuple[str, ...]
) -> subprocess.CompletedProcess[str]:
    """Run a git subcommand in a working directory with a bounded timeout.

    Args:
        working_directory: Directory to run git in (passed via 'git -C').
        all_git_arguments: The git subcommand and its arguments.

    Returns:
        The completed process with captured text stdout and stderr.
    """
    return subprocess.run(
        [
            GIT_EXECUTABLE,
            GIT_DIRECTORY_FLAG,
            str(working_directory),
            *all_git_arguments,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS,
    )


def is_inside_work_tree(working_directory: Path) -> bool:
    """Report whether the working directory is inside a git work tree.

    Args:
        working_directory: Directory to test.

    Returns:
        True when 'git rev-parse --is-inside-work-tree' prints 'true'.
    """
    completed = _run_git(working_directory, ALL_GIT_IS_INSIDE_WORK_TREE_ARGS)
    return completed.returncode == 0 and (
        completed.stdout.strip() == GIT_INSIDE_WORK_TREE_TRUE
    )


def worktree_machinery_is_healthy(working_directory: Path) -> bool:
    """Report whether git worktree machinery works in the working directory.

    EnterWorktree relies on 'git worktree' to create and enter the branch
    worktree; a failing worktree list means it cannot.

    Args:
        working_directory: Directory to test.

    Returns:
        True when 'git worktree list' exits cleanly.
    """
    completed = _run_git(working_directory, ALL_GIT_WORKTREE_LIST_ARGS)
    return completed.returncode == 0


def classify_environment(
    working_directory: Path, pr_identity: RepoIdentity
) -> PreflightVerdict:
    """Classify the working directory against the target PR repository.

    Args:
        working_directory: The session's current working directory.
        pr_identity: The PR's owner/repo (lower-cased for comparison).

    Returns:
        A PreflightVerdict naming the outcome and the worktree-machinery health.
    """
    if not is_inside_work_tree(working_directory):
        return PreflightVerdict(OUTCOME_RE_ROOTED, None, False)
    has_healthy_machinery = worktree_machinery_is_healthy(working_directory)
    remote = _run_git(working_directory, ALL_GIT_REMOTE_GET_URL_ARGS)
    if remote.returncode != 0:
        return PreflightVerdict(OUTCOME_RE_ROOTED, None, has_healthy_machinery)
    cwd_identity = parse_repo_identity(remote.stdout)
    if cwd_identity is None:
        return PreflightVerdict(OUTCOME_DIFFERENT_REPO, None, has_healthy_machinery)
    if cwd_identity == pr_identity:
        return PreflightVerdict(OUTCOME_SAME_REPO, cwd_identity, has_healthy_machinery)
    return PreflightVerdict(OUTCOME_DIFFERENT_REPO, cwd_identity, has_healthy_machinery)


def decide_exit_code(verdict: PreflightVerdict, mode: str) -> int:
    """Decide the process exit code from a classification and the mode.

    Args:
        verdict: The classification of the working directory.
        mode: MODE_STRICT (autoconverge) or MODE_CLASSIFY (pr-converge).

    Returns:
        EXIT_PREFLIGHT_OK when it is safe to continue, else EXIT_PREFLIGHT_ABORT.
    """
    if verdict.outcome == OUTCOME_RE_ROOTED:
        return EXIT_PREFLIGHT_ABORT
    if verdict.outcome == OUTCOME_SAME_REPO:
        if not verdict.has_healthy_worktree_machinery:
            return EXIT_PREFLIGHT_ABORT
        return EXIT_PREFLIGHT_OK
    if mode == MODE_STRICT:
        return EXIT_PREFLIGHT_ABORT
    return EXIT_PREFLIGHT_OK


def _cwd_identity_labels(verdict: PreflightVerdict) -> tuple[str, str]:
    """Return display labels for the working directory's owner and repo.

    Args:
        verdict: The classification of the working directory.

    Returns:
        The lower-cased owner and repo, or the unknown placeholder for each
        when the working directory identity could not be parsed.
    """
    if verdict.cwd_identity is None:
        return CWD_IDENTITY_UNKNOWN, CWD_IDENTITY_UNKNOWN
    return verdict.cwd_identity.owner, verdict.cwd_identity.repo


def _same_repo_lines(
    verdict: PreflightVerdict, working_directory: Path, pr_identity: RepoIdentity
) -> list[str]:
    """Build the report lines for the same-repo outcome.

    Args:
        verdict: The classification of the working directory.
        working_directory: The session's current working directory.
        pr_identity: The PR's owner/repo.

    Returns:
        A summary line, plus an abort line when the worktree machinery is broken.
    """
    report_lines = [
        SUMMARY_SAME_REPO_TEMPLATE.format(
            owner=pr_identity.owner, repo=pr_identity.repo
        )
    ]
    if not verdict.has_healthy_worktree_machinery:
        report_lines.append(
            ABORT_WORKTREE_BROKEN_TEMPLATE.format(cwd=working_directory)
        )
    return report_lines


def _different_repo_lines(
    verdict: PreflightVerdict, mode: str, pr_identity: RepoIdentity
) -> list[str]:
    """Build the report lines for the different-repo outcome.

    Args:
        verdict: The classification of the working directory.
        mode: MODE_STRICT (autoconverge) or MODE_CLASSIFY (pr-converge).
        pr_identity: The PR's owner/repo.

    Returns:
        A summary line, plus an abort line under strict mode or a route line
        under classify mode.
    """
    cwd_owner, cwd_repo = _cwd_identity_labels(verdict)
    report_lines = [
        SUMMARY_DIFFERENT_REPO_TEMPLATE.format(
            cwd_owner=cwd_owner,
            cwd_repo=cwd_repo,
            owner=pr_identity.owner,
            repo=pr_identity.repo,
        )
    ]
    if mode == MODE_STRICT:
        report_lines.append(
            ABORT_DIFFERENT_REPO_STRICT_TEMPLATE.format(
                cwd_owner=cwd_owner,
                cwd_repo=cwd_repo,
                owner=pr_identity.owner,
                repo=pr_identity.repo,
            )
        )
    else:
        report_lines.append(
            ROUTE_DIFFERENT_REPO_TEMPLATE.format(
                owner=pr_identity.owner, repo=pr_identity.repo
            )
        )
    return report_lines


def _re_rooted_lines(working_directory: Path, pr_identity: RepoIdentity) -> list[str]:
    """Build the report lines for the re-rooted outcome.

    Args:
        working_directory: The session's current working directory.
        pr_identity: The PR's owner/repo.

    Returns:
        A summary line and an abort line with the recovery instruction.
    """
    return [
        SUMMARY_RE_ROOTED_TEMPLATE.format(cwd=working_directory),
        ABORT_RE_ROOTED_TEMPLATE.format(owner=pr_identity.owner, repo=pr_identity.repo),
    ]


def build_report_lines(
    verdict: PreflightVerdict,
    mode: str,
    working_directory: Path,
    pr_identity: RepoIdentity,
) -> list[str]:
    """Build the stdout report lines for a classification.

    Args:
        verdict: The classification of the working directory.
        mode: MODE_STRICT (autoconverge) or MODE_CLASSIFY (pr-converge).
        working_directory: The session's current working directory.
        pr_identity: The PR's owner/repo.

    Returns:
        Lines to print: the machine-readable outcome marker first, then a
        summary and a recovery or routing instruction when relevant.
    """
    report_lines = [OUTCOME_MARKER_TEMPLATE.format(outcome=verdict.outcome)]
    if verdict.outcome == OUTCOME_SAME_REPO:
        report_lines.extend(_same_repo_lines(verdict, working_directory, pr_identity))
    elif verdict.outcome == OUTCOME_DIFFERENT_REPO:
        report_lines.extend(_different_repo_lines(verdict, mode, pr_identity))
    else:
        report_lines.extend(_re_rooted_lines(working_directory, pr_identity))
    return report_lines


def main(all_arguments: list[str]) -> int:
    """Classify the working directory and report whether the run can continue.

    Args:
        all_arguments: The argument vector (sys.argv[1:] in normal use).

    Returns:
        The process exit code (EXIT_PREFLIGHT_OK or EXIT_PREFLIGHT_ABORT).
    """
    parser = argparse.ArgumentParser(description=PREFLIGHT_CLI_DESCRIPTION)
    parser.add_argument(OWNER_ARG_FLAG, required=True)
    parser.add_argument(REPO_ARG_FLAG, required=True)
    parser.add_argument(MODE_ARG_FLAG, required=True, choices=ALL_PREFLIGHT_MODES)
    parsed_arguments = parser.parse_args(all_arguments)
    pr_identity = RepoIdentity(
        owner=parsed_arguments.owner.lower(),
        repo=parsed_arguments.repo.lower(),
    )
    working_directory = Path.cwd()
    try:
        verdict = classify_environment(working_directory, pr_identity)
    except subprocess.TimeoutExpired:
        print(
            OUTCOME_MARKER_TEMPLATE.format(outcome=OUTCOME_RE_ROOTED),
            file=sys.stdout,
        )
        print(
            ABORT_RE_ROOTED_TEMPLATE.format(
                owner=pr_identity.owner, repo=pr_identity.repo
            ),
            file=sys.stdout,
        )
        return EXIT_PREFLIGHT_ABORT
    for each_report_line in build_report_lines(
        verdict, parsed_arguments.mode, working_directory, pr_identity
    ):
        print(each_report_line, file=sys.stdout)
    return decide_exit_code(verdict, parsed_arguments.mode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
