#!/usr/bin/env python3
"""PreToolUse hook: fetch origin's default branch before EnterWorktree creates one.

``EnterWorktree`` in its default ``fresh`` mode bases a new worktree on the
locally cached ``refs/remotes/origin/<default-branch>`` ref and only runs
``git fetch`` when that ref is missing entirely -- so a worktree created
without a recent fetch silently starts behind the remote. This hook fetches
that ref immediately before the tool resolves its base, so the ref it reads
is current.

::

    EnterWorktree({})                              # tool_input has no "path"
             |
             v
    this hook: git fetch origin <default-branch>   # best-effort, never blocks
             |
             v
    EnterWorktree resolves refs/remotes/origin/<default-branch>  # now fresh

The hook is a no-op when ``tool_input`` carries a ``path`` (switching into an
already-existing worktree needs no fresh base) and always exits 0 -- a failed
or slow fetch never blocks worktree creation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants import (  # noqa: E402
    enter_worktree_prefetch_constants as prefetch_constants,
)
from hooks_constants import (
    pre_tool_use_stdin,
)


def is_enter_worktree_creation(payload_by_field: dict[str, object]) -> bool:
    """Return True when this hook invocation is an EnterWorktree creation call.

    Args:
        payload_by_field: The full PreToolUse hook payload (already JSON-parsed),
            keyed by top-level field name.

    Returns:
        True when ``tool_name == "EnterWorktree"`` and ``tool_input`` carries
        no ``path`` key. A ``path`` value means the call switches into an
        already-existing worktree rather than creating one, so it is False
        for that case and for every other tool.
    """
    if payload_by_field.get("tool_name", "") != prefetch_constants.ENTER_WORKTREE_TOOL_NAME:
        return False
    tool_input = payload_by_field.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return True
    return not tool_input.get(prefetch_constants.ENTER_WORKTREE_PATH_INPUT_KEY)


def _run_git_quietly(
    repo_directory: str,
    all_git_arguments: list[str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str] | None:
    """Run ``git`` with the given arguments, or return None when it cannot run.

    Args:
        repo_directory: Working directory to run ``git`` in.
        all_git_arguments: The git subcommand and its arguments, without the
            leading ``"git"`` (for example ``["fetch", "origin", "main"]``).
        timeout_seconds: Seconds to wait before abandoning the command.

    Returns:
        The completed process, or None when git is unavailable, the OS refuses
        to start it, or the command exceeds ``timeout_seconds``.
    """
    try:
        return subprocess.run(
            ["git", *all_git_arguments],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=repo_directory,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def resolve_origin_default_branch(repo_directory: str) -> str | None:
    """Return the branch name origin's HEAD points at, or None if unresolved.

    Args:
        repo_directory: Working directory to run ``git`` in.

    Returns:
        The branch name (for example ``"main"``) parsed from
        ``refs/remotes/origin/HEAD``, or None when the symbolic ref is
        unset, git is unavailable, or the command times out.
    """
    completed_process = _run_git_quietly(
        repo_directory,
        ["symbolic-ref", prefetch_constants.ORIGIN_HEAD_SYMBOLIC_REF],
        prefetch_constants.GIT_SYMBOLIC_REF_TIMEOUT_SECONDS,
    )
    if completed_process is None:
        return None
    if completed_process.returncode != 0:
        return None
    resolved_ref = completed_process.stdout.strip()
    origin_ref_prefix = prefetch_constants.ORIGIN_REMOTE_REF_PREFIX
    if not resolved_ref.startswith(origin_ref_prefix):
        return None
    return resolved_ref[len(origin_ref_prefix):]


def fetch_origin_branch(repo_directory: str, branch_name: str) -> None:
    """Best-effort ``git fetch origin <branch_name>``; never raises.

    Args:
        repo_directory: Working directory to run ``git`` in.
        branch_name: Branch to fetch from the ``origin`` remote.
    """
    _run_git_quietly(
        repo_directory,
        ["fetch", prefetch_constants.ORIGIN_REMOTE_NAME, branch_name],
        prefetch_constants.GIT_FETCH_TIMEOUT_SECONDS,
    )


def main() -> None:
    """Entry point for the PreToolUse:EnterWorktree hook.

    Reads the PreToolUse payload from stdin, and when it is an EnterWorktree
    creation call, fetches origin's default branch in the session's ``cwd``
    before returning. Always exits 0: a fetch failure self-heals on the next
    fetch rather than blocking worktree creation.
    """
    hook_payload = pre_tool_use_stdin.read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        sys.exit(0)
    if not is_enter_worktree_creation(hook_payload):
        sys.exit(0)
    repo_directory = hook_payload.get("cwd")
    if not isinstance(repo_directory, str) or not repo_directory:
        sys.exit(0)
    default_branch = resolve_origin_default_branch(repo_directory)
    if default_branch is None:
        sys.exit(0)
    fetch_origin_branch(repo_directory, default_branch)
    sys.exit(0)


if __name__ == "__main__":
    main()
