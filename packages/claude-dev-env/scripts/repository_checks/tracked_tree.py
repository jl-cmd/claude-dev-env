"""List tracked worktree paths for the committed-tree checker."""

from __future__ import annotations

from pathlib import Path

from policy_lint.selection_git import git_bytes_for, split_nul_tokens

from repository_checks.config.constants import ALL_GIT_LS_FILES_ARGUMENTS


def tracked_relative_paths(repository_root: Path) -> tuple[str, ...]:
    """Return tracked paths as repository-relative posix strings.

    ::

        git ls-files -z  ->  ("notes/CLAUDE.md", "src/app.py")
        ok:   paths are relative
        flag: an absolute Windows path

    Args:
        repository_root: Git repository root.

    Returns:
        Tracked relative paths in Git order.
    """
    raw_paths = git_bytes_for(repository_root, ALL_GIT_LS_FILES_ARGUMENTS)
    return split_nul_tokens(raw_paths)
