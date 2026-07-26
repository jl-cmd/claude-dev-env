"""Git repository probes and checkout-state handling for the split-pr scripts.

::

    starting_state = read_starting_state(repo_root)
    # ok:   "main" on a branch, else the detached commit sha
    restore_starting_state(repo_root, starting_state)
    # ok:   None when the checkout returned cleanly

Each probe answers one question about the repository. The starting-state pair
lets a caller leave the working tree exactly where it found it, whether the run
finished or failed part way through a stack.
"""

from __future__ import annotations

from pathlib import Path

from split_pr_process_runner import read_failure_detail, run_checked_git, run_git
from split_pr_scripts_constants.config.common_constants import ALL_EMPTY_ERROR_CONTEXT
from split_pr_scripts_constants.config.execute_constants import (
    ERROR_EXECUTE_FAILED,
    GIT_BRANCH,
    GIT_CHECKOUT,
    GIT_FORCE_FLAG,
    GIT_HEAD_REF,
    GIT_LIST_FLAG,
    GIT_ORIGIN_PREFIX,
    GIT_PORCELAIN,
    GIT_QUIET_FLAG,
    GIT_REFS_HEADS_PREFIX,
    GIT_REFS_REMOTES_PREFIX,
    GIT_REMOTE,
    GIT_REV_PARSE,
    GIT_SHORT_FLAG,
    GIT_SHOW_REF,
    GIT_STATUS,
    GIT_SYMBOLIC_REF,
    GIT_VERIFY_FLAG,
)


def is_working_tree_dirty(repo_root: Path) -> bool:
    """Report whether the worktree holds uncommitted changes.

    Args:
        repo_root: Git repository toplevel.

    Returns:
        True when ``git status --porcelain`` prints anything.

    Raises:
        RuntimeError: When git cannot read the status.
    """
    completed = run_checked_git(
        [GIT_STATUS, GIT_PORCELAIN],
        repo_root,
        ERROR_EXECUTE_FAILED,
        ALL_EMPTY_ERROR_CONTEXT,
    )
    return bool(completed.stdout.strip())


def branch_exists(repo_root: Path, branch_name: str) -> bool:
    """Report whether a local branch of this exact name is present.

    Args:
        repo_root: Git repository toplevel.
        branch_name: Branch to look for.

    Returns:
        True when ``git branch --list`` names it.
    """
    completed = run_git([GIT_BRANCH, GIT_LIST_FLAG, branch_name], repo_root)
    return bool(completed.stdout.strip())


def show_ref_verifies(repo_root: Path, full_ref: str) -> bool:
    """Report whether git resolves full_ref as written.

    Args:
        repo_root: Git repository toplevel.
        full_ref: Fully qualified ref, such as ``refs/heads/main``.

    Returns:
        True when ``git show-ref --verify`` succeeds.
    """
    completed = run_git(
        [GIT_SHOW_REF, GIT_VERIFY_FLAG, GIT_QUIET_FLAG, full_ref],
        repo_root,
    )
    return completed.returncode == 0


def remote_ref_exists(repo_root: Path, remote_ref_name: str) -> bool:
    """Report whether ``refs/remotes/<remote_ref_name>`` is present.

    Args:
        repo_root: Git repository toplevel.
        remote_ref_name: Remote-tracking name, such as ``origin/main``.

    Returns:
        True when the remote-tracking ref resolves.
    """
    return show_ref_verifies(repo_root, f"{GIT_REFS_REMOTES_PREFIX}{remote_ref_name}")


def local_branch_ref_exists(repo_root: Path, ref_name: str) -> bool:
    """Report whether a local branch exists, ignoring any ``origin/`` prefix.

    ::

        local_branch_ref_exists(repo_root, "origin/main")  # ok: probes main
        local_branch_ref_exists(repo_root, "main")         # ok: probes main

    Args:
        repo_root: Git repository toplevel.
        ref_name: Branch name, with or without the remote prefix.

    Returns:
        True when ``refs/heads/<name>`` resolves.
    """
    local_name = (
        ref_name[len(GIT_ORIGIN_PREFIX) :]
        if ref_name.startswith(GIT_ORIGIN_PREFIX)
        else ref_name
    )
    return show_ref_verifies(repo_root, f"{GIT_REFS_HEADS_PREFIX}{local_name}")


def remote_exists(repo_root: Path, remote_name: str) -> bool:
    """Report whether the repository has a remote of this name.

    Args:
        repo_root: Git repository toplevel.
        remote_name: Remote to look for, such as ``origin``.

    Returns:
        True when ``git remote`` lists it.
    """
    completed = run_git([GIT_REMOTE], repo_root)
    if completed.returncode != 0:
        return False
    all_remote_names = {
        each_line.strip()
        for each_line in completed.stdout.splitlines()
        if each_line.strip()
    }
    return remote_name in all_remote_names


def read_starting_state(repo_root: Path) -> str:
    """Return the ref to come back to: the checked-out branch, else its commit.

    Args:
        repo_root: Git repository toplevel.

    Returns:
        Branch name when HEAD is attached, otherwise the HEAD commit sha.

    Raises:
        RuntimeError: When git can read neither the branch nor the commit.
    """
    branch_completed = run_git(
        [GIT_SYMBOLIC_REF, GIT_QUIET_FLAG, GIT_SHORT_FLAG, GIT_HEAD_REF],
        repo_root,
    )
    branch_name = branch_completed.stdout.strip()
    if branch_completed.returncode == 0 and branch_name:
        return branch_name
    commit_completed = run_checked_git(
        [GIT_REV_PARSE, GIT_HEAD_REF],
        repo_root,
        ERROR_EXECUTE_FAILED,
        ALL_EMPTY_ERROR_CONTEXT,
    )
    return commit_completed.stdout.strip()


def restore_starting_state(repo_root: Path, starting_state: str) -> str | None:
    """Return to starting_state, discarding staged slice work.

    Args:
        repo_root: Git repository toplevel.
        starting_state: Branch name or commit sha to check out.

    Returns:
        None when the checkout succeeded, else the git failure text.
    """
    completed = run_git([GIT_CHECKOUT, GIT_FORCE_FLAG, starting_state], repo_root)
    if completed.returncode == 0:
        return None
    return read_failure_detail(completed)
