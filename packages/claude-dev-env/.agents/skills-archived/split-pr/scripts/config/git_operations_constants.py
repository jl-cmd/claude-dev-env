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
RECORD_KEY_COMMIT_SHA: str = "commit_sha"
RECORD_KEY_BASE_SHA: str = "base_sha"
RECORD_KEY_ALL_PATHS: str = "all_paths"
RECORD_KEY_EXIT_CODE: str = "exit_code"
ERROR_DIRTY_TREE: str = "working tree is dirty; refuse materialization"
ERROR_COMMIT_FAILED: str = "git commit failed for slice"
ERROR_CHECKOUT_FAILED: str = "git checkout restore failed"
ERROR_ADD_FAILED: str = "git add failed for slice paths"
ERROR_EMPTY_SLICE_PATHS: str = "slice path list is empty"
ERROR_REV_PARSE_FAILED: str = "rev-parse HEAD failed"
ERROR_STATUS_FAILED: str = "git status failed"
ERROR_RESTORE_FAILED: str = "git restore failed"
ERROR_CLEAN_FAILED: str = "git clean failed"
ERROR_BASE_MISMATCH_TEMPLATE: str = (
    "HEAD {head_sha} does not match expected base {expected_base_sha}"
)
GIT_FORCE_FLAG: str = "--force"
GIT_PATHSPEC_SEPARATOR: str = "--"
