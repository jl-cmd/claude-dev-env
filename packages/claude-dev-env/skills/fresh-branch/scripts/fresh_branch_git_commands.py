"""Git commands behind the fresh-branch worktree creator.

::

    create_worktree_branch(repo_root, "fix/x", worktree_path, "origin/main")
    # ok:   git worktree add -b fix/x --no-track <path> origin/main
    # flag: git worktree add -b fix/x <path> origin/main

Git auto-tracks a remote-tracking start point, leaving the new branch with
``branch.<name>.merge = refs/heads/main``. Under ``push.default = upstream`` a
bare ``git push`` from that branch fast-forwards straight onto main, so every
worktree here is created with ``GIT_NO_TRACK_FLAG``.

Each command reports failure by raising, so callers never read a return code.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from fresh_branch_scripts_constants.fresh_branch_cli_constants import (
    ERROR_BASE_COMMIT_LOOKUP,
    ERROR_BASE_REF_MISSING,
    ERROR_BRANCH_NAME_UNSAFE,
    ERROR_FETCH_FAILED,
    ERROR_REPO_NOT_GIT,
    ERROR_WORKTREE_FAILED,
    GIT_BRANCH_FLAG,
    GIT_BRANCH_FORMAT_FLAG,
    GIT_CHECK_REF_FORMAT,
    GIT_COMMAND,
    GIT_FETCH,
    GIT_NO_TRACK_FLAG,
    GIT_QUIET_FLAG,
    GIT_REFS_REMOTES_PREFIX,
    GIT_REMOTE_NAME_ORIGIN,
    GIT_REMOTE_PREFIX,
    GIT_REV_PARSE,
    GIT_SHOW_REF,
    GIT_SHOW_TOPLEVEL,
    GIT_VERIFY_FLAG,
    GIT_WORKTREE,
    GIT_WORKTREE_ADD,
)


def run_git(
    all_git_arguments: list[str],
    working_directory: Path,
) -> subprocess.CompletedProcess[str]:
    """Run one git command and capture its output without raising.

    Args:
        all_git_arguments: Arguments that follow the ``git`` executable.
        working_directory: Directory the command runs in.

    Returns:
        The completed process, carrying return code and captured text.
    """
    return subprocess.run(
        [GIT_COMMAND, *all_git_arguments],
        cwd=str(working_directory),
        check=False,
        capture_output=True,
        text=True,
    )


def assert_git_accepts_branch_name(branch_name: str) -> None:
    """Raise when git rejects branch_name as a branch ref format.

    ::

        assert_git_accepts_branch_name("fix/x")   # ok: returns None
        assert_git_accepts_branch_name("fix..x")  # flag: ValueError

    Args:
        branch_name: Candidate branch name.

    Raises:
        ValueError: When ``git check-ref-format`` rejects the name.
    """
    completed = run_git(
        [GIT_CHECK_REF_FORMAT, GIT_BRANCH_FORMAT_FLAG, branch_name],
        working_directory=Path.cwd(),
    )
    if completed.returncode != 0:
        raise ValueError(ERROR_BRANCH_NAME_UNSAFE)


def resolve_repo_root(repo_path: Path) -> Path:
    """Return the git toplevel directory holding repo_path.

    Args:
        repo_path: Any path inside the source repository.

    Returns:
        The repository root directory.

    Raises:
        RuntimeError: When repo_path is not inside a git repository.
    """
    completed = run_git(
        [GIT_REV_PARSE, GIT_SHOW_TOPLEVEL],
        working_directory=repo_path,
    )
    if completed.returncode != 0:
        raise RuntimeError(ERROR_REPO_NOT_GIT % repo_path)
    return Path(completed.stdout.strip())


def fetch_base_ref(repo_root: Path, base_ref: str) -> None:
    """Fetch base_ref into repo_root and confirm the ref then exists.

    Args:
        repo_root: Source repository root.
        base_ref: Ref to fetch, such as ``origin/main``.

    Raises:
        RuntimeError: When the fetch fails or the ref is still absent.
    """
    remote_name, remote_branch = split_remote_ref(base_ref)
    completed = run_git(
        [GIT_FETCH, remote_name, remote_branch],
        working_directory=repo_root,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            ERROR_FETCH_FAILED % (base_ref, read_failure_text(completed)),
        )
    if not is_ref_present(repo_root, base_ref):
        raise RuntimeError(ERROR_BASE_REF_MISSING % base_ref)


def resolve_base_commit(repo_root: Path, base_ref: str) -> str:
    """Return the commit SHA that base_ref points at.

    Args:
        repo_root: Source repository root.
        base_ref: Ref to resolve, such as ``origin/main``.

    Returns:
        The full commit SHA at base_ref.

    Raises:
        RuntimeError: When git cannot resolve the ref to a commit.
    """
    completed = run_git(
        [GIT_REV_PARSE, base_ref],
        working_directory=repo_root,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            ERROR_BASE_COMMIT_LOOKUP % (base_ref, read_failure_text(completed)),
        )
    return completed.stdout.strip()


def create_worktree_branch(
    repo_root: Path,
    branch_name: str,
    worktree_path: Path,
    base_ref: str,
) -> None:
    """Create branch_name at base_ref in a new worktree, with no upstream.

    ::

        create_worktree_branch(repo_root, "fix/x", path, "origin/main")
        # ok:   branch.fix/x.merge is unset
        # flag: branch.fix/x.merge = refs/heads/main  (auto-tracked)

    Args:
        repo_root: Source repository root.
        branch_name: New branch to create.
        worktree_path: Directory that will hold the new worktree.
        base_ref: Start point for the new branch.

    Raises:
        RuntimeError: When ``git worktree add`` fails.
    """
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    completed = run_git(
        build_worktree_add_arguments(branch_name, worktree_path, base_ref),
        working_directory=repo_root,
    )
    if completed.returncode != 0:
        raise RuntimeError(ERROR_WORKTREE_FAILED % read_failure_text(completed))


def build_worktree_add_arguments(
    branch_name: str,
    worktree_path: Path,
    base_ref: str,
) -> list[str]:
    """Return the ``git worktree add`` argument list, including --no-track.

    ::

        build_worktree_add_arguments("fix/x", Path("/tmp/x"), "origin/main")
        # ok: ["worktree", "add", "-b", "fix/x", "--no-track", "/tmp/x",
        #      "origin/main"]

    Args:
        branch_name: New branch to create.
        worktree_path: Directory that will hold the new worktree.
        base_ref: Start point for the new branch.

    Returns:
        Arguments to pass to ``run_git``.
    """
    return [
        GIT_WORKTREE,
        GIT_WORKTREE_ADD,
        GIT_BRANCH_FLAG,
        branch_name,
        GIT_NO_TRACK_FLAG,
        str(worktree_path),
        base_ref,
    ]


def split_remote_ref(base_ref: str) -> tuple[str, str]:
    """Split base_ref into its remote name and branch name.

    ::

        split_remote_ref("origin/main")   # ok: ("origin", "main")
        split_remote_ref("upstream/dev")  # ok: ("upstream", "dev")
        split_remote_ref("main")          # ok: ("origin", "main")

    Args:
        base_ref: Base ref or bare branch name.

    Returns:
        The remote name and the branch name to fetch.
    """
    if base_ref.startswith(GIT_REMOTE_PREFIX):
        return GIT_REMOTE_NAME_ORIGIN, base_ref[len(GIT_REMOTE_PREFIX) :]
    if "/" in base_ref:
        remote_name, remote_branch = base_ref.split("/", 1)
        return remote_name, remote_branch
    return GIT_REMOTE_NAME_ORIGIN, base_ref


def is_ref_present(repo_root: Path, base_ref: str) -> bool:
    """Report whether base_ref resolves in repo_root.

    Checks the remote-tracking ref first, then base_ref as written, so both
    ``origin/main`` and a local tag or branch answer correctly.

    Args:
        repo_root: Source repository root.
        base_ref: Ref to look for.

    Returns:
        True when git resolves the ref.
    """
    remote_ref = f"{GIT_REFS_REMOTES_PREFIX}{base_ref}"
    completed = run_git(
        [GIT_SHOW_REF, GIT_VERIFY_FLAG, GIT_QUIET_FLAG, remote_ref],
        working_directory=repo_root,
    )
    if completed.returncode == 0:
        return True
    completed = run_git(
        [GIT_REV_PARSE, GIT_VERIFY_FLAG, GIT_QUIET_FLAG, base_ref],
        working_directory=repo_root,
    )
    return completed.returncode == 0


def read_failure_text(completed: subprocess.CompletedProcess[str]) -> str:
    """Return the message a failed git command left behind.

    Args:
        completed: A completed git process with a non-zero return code.

    Returns:
        Trimmed stderr, falling back to trimmed stdout.
    """
    return completed.stderr.strip() or completed.stdout.strip()
