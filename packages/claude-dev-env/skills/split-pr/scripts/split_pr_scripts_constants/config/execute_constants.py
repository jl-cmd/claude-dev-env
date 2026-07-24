"""Constants for execute_split git and gh operations."""

from __future__ import annotations

EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE = 1

PAYLOAD_KEY_ERROR = "error"
PAYLOAD_KEY_DRY_RUN = "dry_run"
PAYLOAD_KEY_CREATED = "created_slices"
PAYLOAD_KEY_PR_URLS = "pr_urls"

GIT_COMMAND = "git"
GIT_FETCH = "fetch"
GIT_CHECKOUT = "checkout"
GIT_BRANCH = "branch"
GIT_ADD = "add"
GIT_COMMIT = "commit"
GIT_PUSH = "push"
GIT_REV_PARSE = "rev-parse"
GIT_SHOW_TOPLEVEL = "--show-toplevel"
GIT_STATUS = "status"
GIT_PORCELAIN = "--porcelain"
GIT_SET_UPSTREAM = "-u"
GIT_MESSAGE_FLAG = "-m"
GIT_ORIGIN = "origin"

GH_COMMAND = "gh"
GH_PR = "pr"
GH_CREATE = "create"
GH_DRAFT = "--draft"
GH_TITLE = "--title"
GH_BODY_FILE = "--body-file"
GH_BASE = "--base"
GH_HEAD = "--head"
GH_REPO_FLAG = "--repo"

DEFAULT_COMMIT_MESSAGE_TEMPLATE = "feat: %s\n\n%s\n\nSplit from PR #%s."

ERROR_DIRTY_TREE = "working tree is dirty; commit or stash before execute_split"
ERROR_REPO_NOT_GIT = "path is not inside a git repository: %s"
ERROR_EXECUTE_FAILED = "execute_split failed: %s"
ERROR_BRANCH_EXISTS = "branch already exists: %s"
ERROR_CHECKOUT_FILES = "failed to checkout files from %s: %s"
ERROR_COMMIT_FAILED = "commit failed on %s: %s"
ERROR_PUSH_FAILED = "push failed for %s: %s"
ERROR_PR_CREATE_FAILED = "gh pr create failed for %s: %s"
ERROR_EMPTY_SLICE_AFTER_CHECKOUT = "no files staged for slice %s after checkout"

JSON_INDENT_SPACES = 2
GIT_REFS_REMOTES_PREFIX = "refs/remotes/"
GIT_REFS_HEADS_PREFIX = "refs/heads/"
MARKDOWN_BODY_SUFFIX = ".md"
GIT_CHECKOUT_FORCE_CREATE = "-B"
GIT_ADD_PATHSPEC = "--"
PAYLOAD_KEY_PARTIAL = "partial"
PAYLOAD_KEY_FAILED_SLICE = "failed_slice"

