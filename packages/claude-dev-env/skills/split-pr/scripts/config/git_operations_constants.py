"""Constants for safe local Git slice materialization."""

from __future__ import annotations

GIT_COMMAND: str = "git"
ALL_GIT_STATUS_PORCELAIN: tuple[str, ...] = ("status", "--porcelain")
ALL_GIT_REV_PARSE_HEAD: tuple[str, ...] = ("rev-parse", "HEAD")
GIT_CHECKOUT: str = "checkout"
GIT_ADD: str = "add"
GIT_COMMIT: str = "commit"
GIT_COMMIT_MESSAGE_FLAG: str = "-m"
ALL_GIT_RESTORE_STAGED_WORKTREE: tuple[str, ...] = (
    "restore",
    "--staged",
    "--worktree",
    ".",
)
ALL_GIT_CLEAN_FORCE_DIR: tuple[str, ...] = ("clean", "-fd")
ERROR_DIRTY_TREE: str = "working tree is dirty; refuse materialization"
ERROR_COMMIT_FAILED: str = "git commit failed for slice"
ERROR_CHECKOUT_FAILED: str = "git checkout restore failed"
ERROR_ADD_FAILED: str = "git add failed for slice paths"
