"""Materialize verified split slices as local Git commits with restore safety.

::

    outcome = materialize_slice_commit(
        repository_path=repo,
        all_slice_paths=["a.py"],
        commit_message="chore: config slice",
        expected_base_sha=head_before,
        run=run_process,
    )
    # on failure, repository returns to expected_base_sha with clean tree
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from config.git_operations_constants import (
    ALL_GIT_CLEAN_FORCE_DIR,
    ALL_GIT_RESTORE_STAGED_WORKTREE,
    ALL_GIT_REV_PARSE_HEAD,
    ALL_GIT_STATUS_PORCELAIN,
    ERROR_ADD_FAILED,
    ERROR_CHECKOUT_FAILED,
    ERROR_COMMIT_FAILED,
    ERROR_DIRTY_TREE,
    GIT_ADD,
    GIT_CHECKOUT,
    GIT_COMMAND,
    GIT_COMMIT,
    GIT_COMMIT_MESSAGE_FLAG,
)
from config.plan_constants import EXIT_CODE_SUCCESS
from split_pr_process_runner import CapturedProcessOutcome, run_process

ProcessRunner = Callable[[list[str], str], CapturedProcessOutcome]
JsonObject = dict[str, object]


def _git(
    run: ProcessRunner,
    repository_path: Path,
    all_git_args: list[str],
) -> CapturedProcessOutcome:
    return run([GIT_COMMAND, *all_git_args], str(repository_path))


def read_head_sha(repository_path: Path, run: ProcessRunner = run_process) -> str:
    """Return the current HEAD commit SHA.

    Args:
        repository_path: Git repository root.
        run: Process runner (injectable for tests).

    Returns:
        Stripped HEAD sha text.

    Raises:
        RuntimeError: When rev-parse fails.
    """
    outcome = _git(run, repository_path, list(ALL_GIT_REV_PARSE_HEAD))
    if not outcome.is_success:
        raise RuntimeError(outcome.stderr_text or "rev-parse HEAD failed")
    return outcome.stdout_text.strip()


def assert_clean_worktree(
    repository_path: Path,
    run: ProcessRunner = run_process,
) -> None:
    """Refuse materialization when the worktree is dirty.

    Args:
        repository_path: Git repository root.
        run: Process runner.

    Raises:
        RuntimeError: When porcelain status is non-empty or the command fails.
    """
    outcome = _git(run, repository_path, list(ALL_GIT_STATUS_PORCELAIN))
    if not outcome.is_success:
        raise RuntimeError(outcome.stderr_text or "git status failed")
    if outcome.stdout_text.strip():
        raise RuntimeError(ERROR_DIRTY_TREE)


def restore_repository_state(
    repository_path: Path,
    target_sha: str,
    run: ProcessRunner = run_process,
) -> None:
    """Checkout target_sha and discard uncommitted changes.

    Args:
        repository_path: Git repository root.
        target_sha: Commit to restore.
        run: Process runner.

    Raises:
        RuntimeError: When checkout or clean fails.
    """
    checkout = _git(run, repository_path, [GIT_CHECKOUT, "--force", target_sha])
    if not checkout.is_success:
        raise RuntimeError(checkout.stderr_text or ERROR_CHECKOUT_FAILED)
    restore = _git(run, repository_path, list(ALL_GIT_RESTORE_STAGED_WORKTREE))
    if not restore.is_success:
        raise RuntimeError(restore.stderr_text or "git restore failed")
    clean = _git(run, repository_path, list(ALL_GIT_CLEAN_FORCE_DIR))
    if not clean.is_success:
        raise RuntimeError(clean.stderr_text or "git clean failed")


def materialize_slice_commit(
    repository_path: Path,
    all_slice_paths: list[str],
    commit_message: str,
    expected_base_sha: str,
    run: ProcessRunner = run_process,
) -> JsonObject:
    """Stage only slice paths and create one commit from a verified base.

    Args:
        repository_path: Git repository root.
        all_slice_paths: Paths relative to the repository for this slice only.
        commit_message: Conventional commit message (already normalized).
        expected_base_sha: HEAD must equal this before staging.
        run: Process runner.

    Returns:
        Map with keys commit_sha, base_sha, all_paths.

    Raises:
        RuntimeError: On dirty tree, base mismatch, add/commit failure, or
            when restore after failure also fails.
    """
    assert_clean_worktree(repository_path, run)
    head_sha = read_head_sha(repository_path, run)
    if head_sha != expected_base_sha:
        raise RuntimeError(
            f"HEAD {head_sha} does not match expected base {expected_base_sha}"
        )
    if not all_slice_paths:
        raise RuntimeError("slice path list is empty")
    try:
        add_outcome = _git(run, repository_path, [GIT_ADD, "--", *all_slice_paths])
        if not add_outcome.is_success:
            raise RuntimeError(add_outcome.stderr_text or ERROR_ADD_FAILED)
        commit_outcome = _git(
            run,
            repository_path,
            [GIT_COMMIT, GIT_COMMIT_MESSAGE_FLAG, commit_message],
        )
        if not commit_outcome.is_success:
            raise RuntimeError(commit_outcome.stderr_text or ERROR_COMMIT_FAILED)
        new_sha = read_head_sha(repository_path, run)
        return {
            "commit_sha": new_sha,
            "base_sha": expected_base_sha,
            "all_paths": list(all_slice_paths),
            "exit_code": EXIT_CODE_SUCCESS,
        }
    except RuntimeError:
        restore_repository_state(repository_path, expected_base_sha, run)
        raise
