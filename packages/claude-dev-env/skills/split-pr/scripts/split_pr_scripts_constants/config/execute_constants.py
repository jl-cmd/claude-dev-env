"""Constants for execute_split git and gh operations."""

from __future__ import annotations

from pathlib import Path

FRESH_BRANCH_SCRIPTS_DIRECTORY = (
    Path(__file__).resolve().parents[4] / "fresh-branch" / "scripts"
)

EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE = 1

PAYLOAD_KEY_ERROR = "error"
PAYLOAD_KEY_DRY_RUN = "dry_run"
PAYLOAD_KEY_CREATED = "created_slices"
PAYLOAD_KEY_PR_URLS = "pr_urls"
PAYLOAD_KEY_SUPERSEDE = "supersede"
PAYLOAD_KEY_COMMENTED = "commented"
PAYLOAD_KEY_CLOSED = "closed"
PAYLOAD_KEY_CHILD_PR_NUMBERS = "child_pr_numbers"
PAYLOAD_KEY_SKIPPED = "skipped"
PAYLOAD_KEY_SKIP_REASON = "skip_reason"
PAYLOAD_KEY_SKIPPED_SLICES = "skipped_slices"
PAYLOAD_KEY_RESTORE_ERROR = "restore_error"

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
GIT_REMOTE = "remote"
GIT_SHOW_REF = "show-ref"
GIT_VERIFY_FLAG = "--verify"
GIT_QUIET_FLAG = "--quiet"
GIT_LIST_FLAG = "--list"
GIT_FORCE_FLAG = "--force"
GIT_DELETE_BRANCH_FLAG = "-D"
GIT_REMOVE = "rm"
GIT_ABBREV_REF_FLAG = "--abbrev-ref"
GIT_SYMBOLIC_REF = "symbolic-ref"
GIT_SHORT_FLAG = "--short"
GIT_HEAD_REF = "HEAD"

GH_COMMAND = "gh"
GH_PR = "pr"
GH_CREATE = "create"
GH_COMMENT = "comment"
GH_CLOSE = "close"
GH_VIEW = "view"
GH_DRAFT = "--draft"
GH_TITLE = "--title"
GH_BODY_FILE = "--body-file"
GH_BASE = "--base"
GH_HEAD = "--head"
GH_REPO_FLAG = "--repo"
GH_JSON = "--json"

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
ERROR_SUPERSEDE_COMMENT_FAILED = "gh pr comment failed for source #%s: %s"
ERROR_SUPERSEDE_CLOSE_FAILED = "gh pr close failed for source #%s: %s"
ERROR_SUPERSEDE_VIEW_FAILED = "gh pr view failed for source #%s: %s"
ERROR_SUPERSEDE_VIEW_JSON = "gh pr view output is not valid JSON for source #%s: %s"
ERROR_RESTORE_FAILED = "failed to restore the starting checkout (%s): %s"
ERROR_NO_ORIGIN_REMOTE = "remote origin is required to push split branches"
ERROR_SOURCE_HEAD_MOVED = (
    "source branch %s now points at %s but the plan was computed at %s; "
    "re-run analyze_pr and re-approve the plan"
)
ERROR_SOURCE_HEAD_UNREADABLE = "could not read the head commit of %s: %s"
ERROR_SPLIT_OPTIONAL_REFUSED = (
    "plan says the split is optional (%s); pass --allow-optional-split to "
    "execute it anyway"
)
SKIP_REASON_EMPTY_SLICE = "no_change_against_base"
ERROR_PLAN_MISSING_PR_IDENTITY = "plan missing pr identity (title and pr_number)"
PRETTY_FLAG = "--pretty"

JSON_INDENT_SPACES = 2
NEWLINE = "\n"
EMPTY_JSON_OBJECT_TEXT = "{}"
GIT_REFS_REMOTES_PREFIX = "refs/remotes/"
GIT_REFS_HEADS_PREFIX = "refs/heads/"
MARKDOWN_BODY_SUFFIX = ".md"
GIT_CHECKOUT_FORCE_CREATE = "-B"
GIT_ADD_PATHSPEC = "--"
PAYLOAD_KEY_PARTIAL = "partial"
PAYLOAD_KEY_FAILED_SLICE = "failed_slice"

MINIMUM_SLICES_FOR_SUPERSEDE = 2
PR_URL_NUMBER_MARKER = "/pull/"
SUPERSEDE_HEADING = "## Superseded by stacked split"
SUPERSEDE_INTRO = (
    "This PR was file-split into a stacked draft chain. Review and merge the "
    "stack in order; this source PR is superseded by the slices listed below."
)
SUPERSEDE_MERGE_ORDER_LABEL = "**Merge order:**"
SUPERSEDE_MERGE_ORDER_SEPARATOR = " → "
SUPERSEDE_PR_HASH_PREFIX = "#"
SUPERSEDE_LIST_ITEM_TEMPLATE = "%s. #%s — %s"
SUPERSEDE_UNKNOWN_PR_NUMBER = "?"
SUPERSEDE_SKIP_ATOMIC = "atomic_single_slice"
SUPERSEDE_SKIP_NO_CHILD_URLS = "no_child_pr_urls"
SUPERSEDE_SKIP_PARTIAL = "partial_stack"
SUPERSEDE_SKIP_CREATE_PRS_OFF = "create_prs_disabled"
SUPERSEDE_SKIP_ALREADY_DONE = "already_superseded"
SUPERSEDE_SKIP_DISABLED = "supersede_disabled"
GH_STATE_FIELD = "state"
GH_COMMENTS_FIELD = "comments"
GH_COMMENT_BODY_FIELD = "body"
GH_STATE_CLOSED = "CLOSED"
GH_VIEW_FIELDS = "state,comments"

