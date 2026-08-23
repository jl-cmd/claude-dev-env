#!/usr/bin/env python3
"""
Git post-commit hook: Auto-update parent repos when committing in a submodule.

When you commit in a submodule, this hook:
1. Detects if current repo is a submodule of a parent
2. Stages the submodule update in the parent
3. Creates a commit in the parent pointing to the new submodule commit

This prevents the "lost work" issue where submodule commits aren't tracked by parent.
"""

from __future__ import annotations

import subprocess
import sys
from enum import StrEnum
from pathlib import Path

from git_hooks_constants import GIT_COMMAND_SUCCESS_EXIT_CODE, GIT_EXECUTABLE_NAME


class ParentPointerStatus(StrEnum):
    """States returned by a parent pointer update."""

    UPDATED = "updated"
    UNCHANGED = "unchanged"
    FAILED = "failed"


ParentPointerUpdate = tuple[ParentPointerStatus, str]


def execute_git(
    *arguments: str,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    """Run a Git command and return its completed process."""
    try:
        return subprocess.run(
            [GIT_EXECUTABLE_NAME, *arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return subprocess.CompletedProcess(
            [GIT_EXECUTABLE_NAME, *arguments],
            1,
            "",
            str(error),
        )


def run_git(*arguments: str, cwd: Path) -> str:
    """Run a successful Git command and return its trimmed standard output."""
    command_result = execute_git(*arguments, cwd=cwd)
    if command_result.returncode != GIT_COMMAND_SUCCESS_EXIT_CODE:
        return ""
    return command_result.stdout.strip()


def run_git_from_current_directory(*arguments: str) -> str:
    """Run a successful Git command from the hook's current directory."""
    return run_git(*arguments, cwd=Path.cwd())


def find_parent_repo(repo_dir: Path) -> Path | None:
    """Return the Git superproject that owns the current repository."""
    parent_path_text = run_git(
        "rev-parse",
        "--show-superproject-working-tree",
        cwd=repo_dir,
    )
    if not parent_path_text:
        return None

    parent_path = Path(parent_path_text).resolve()
    if not parent_path.is_dir():
        return None
    return parent_path


def find_submodule_path(parent_repo: Path, repo_dir: Path) -> Path | None:
    """Return the submodule path relative to its parent repository."""
    try:
        return repo_dir.resolve().relative_to(parent_repo.resolve())
    except ValueError:
        return None


def build_literal_pathspec(submodule_path: Path) -> str:
    """Build a Git pathspec that treats every path character literally."""
    return f":(literal){submodule_path.as_posix()}"


def get_git_failure_diagnostic(
    command_result: subprocess.CompletedProcess[str],
) -> str:
    """Return the most useful diagnostic from a failed Git command."""
    return command_result.stderr.strip() or command_result.stdout.strip()


def build_parent_commit_message(
    repo_name: str,
    commit_hash: str,
    commit_message: str,
) -> str:
    """Build the parent commit message for a submodule pointer update."""
    return (
        f"chore: update {repo_name} submodule to {commit_hash}\n\n"
        f"Submodule commit: {commit_message}\n\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>"
    )


def update_parent_pointer(
    parent_repo: Path,
    repo_dir: Path,
    commit_hash: str,
    commit_message: str,
) -> ParentPointerUpdate:
    """Commit the current submodule pointer in its parent repository."""
    submodule_path = find_submodule_path(parent_repo, repo_dir)
    if submodule_path is None:
        return ParentPointerStatus.FAILED, "could not resolve the submodule path"

    submodule_reference = build_literal_pathspec(submodule_path)
    add_result = execute_git("add", "--", submodule_reference, cwd=parent_repo)
    if add_result.returncode != GIT_COMMAND_SUCCESS_EXIT_CODE:
        return ParentPointerStatus.FAILED, get_git_failure_diagnostic(add_result)

    staged_difference = execute_git(
        "diff",
        "--cached",
        "--quiet",
        "--",
        submodule_reference,
        cwd=parent_repo,
    )
    if staged_difference.returncode == GIT_COMMAND_SUCCESS_EXIT_CODE:
        return ParentPointerStatus.UNCHANGED, ""
    if staged_difference.returncode != 1:
        return ParentPointerStatus.FAILED, get_git_failure_diagnostic(staged_difference)

    parent_commit_message = build_parent_commit_message(
        repo_dir.name,
        commit_hash,
        commit_message,
    )
    commit_result = execute_git(
        "commit",
        "--only",
        "-m",
        parent_commit_message,
        "--",
        submodule_reference,
        cwd=parent_repo,
    )
    if commit_result.returncode != GIT_COMMAND_SUCCESS_EXIT_CODE:
        return ParentPointerStatus.FAILED, get_git_failure_diagnostic(commit_result)
    return ParentPointerStatus.UPDATED, ""


def main() -> int:
    """Update a parent repository after a submodule commit."""
    repo_path_text = run_git_from_current_directory("rev-parse", "--show-toplevel")
    if not repo_path_text:
        return 0

    repo_dir = Path(repo_path_text).resolve()
    parent_repo = find_parent_repo(repo_dir)
    if parent_repo is None:
        return 0

    commit_msg = run_git("log", "-1", "--pretty=%s", cwd=repo_dir)
    commit_hash = run_git("rev-parse", "HEAD", cwd=repo_dir)
    short_commit_hash = run_git("rev-parse", "--short", "HEAD", cwd=repo_dir)
    if not commit_hash or not short_commit_hash:
        return 0

    print()
    print("=== Submodule Parent Update ===")
    print(f"Submodule: {repo_dir.name} @ {short_commit_hash}")
    print(f"Parent:    {parent_repo}")

    parent_pointer_status, parent_pointer_diagnostic = update_parent_pointer(
        parent_repo,
        repo_dir,
        commit_hash,
        commit_msg,
    )
    if parent_pointer_status is ParentPointerStatus.FAILED:
        print("Parent update failed.")
        if parent_pointer_diagnostic:
            print(f"Git diagnostic: {parent_pointer_diagnostic}")
        return 0
    if parent_pointer_status is ParentPointerStatus.UNCHANGED:
        print("Parent already up to date.")
        return 0

    print("Parent updated successfully.")
    print("================================")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
