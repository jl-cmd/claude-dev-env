"""Constants for execute_split git and gh operations.

Shared CLI, JSON, and gh names come from ``common_constants``. Everything below
belongs to the execute and supersede stages: git subcommands and flags, the
command-line argument names, the draft-PR body text, and the failure messages.
"""

from __future__ import annotations

from pathlib import Path

from .common_constants import FIELD_LIST_SEPARATOR, PATH_SEPARATOR

FRESH_BRANCH_SCRIPTS_DIRECTORY = (
    Path(__file__).resolve().parents[4] / "fresh-branch" / "scripts"
)

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
PAYLOAD_KEY_PARTIAL = "partial"
PAYLOAD_KEY_FAILED_SLICE = "failed_slice"

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
GIT_SYMBOLIC_REF = "symbolic-ref"
GIT_SHORT_FLAG = "--short"
GIT_HEAD_REF = "HEAD"
GIT_CHECKOUT_FORCE_CREATE = "-B"
GIT_ADD_PATHSPEC = "--"
GIT_REFS_REMOTES_PREFIX = "refs/remotes/"
GIT_REFS_HEADS_PREFIX = "refs/heads/"
GIT_ORIGIN_PREFIX = f"{GIT_ORIGIN}{PATH_SEPARATOR}"

GH_CREATE = "create"
GH_COMMENT = "comment"
GH_CLOSE = "close"
GH_DRAFT = "--draft"
GH_TITLE = "--title"
GH_BODY_FILE = "--body-file"
GH_BASE = "--base"
GH_HEAD = "--head"
GH_STATE_FIELD = "state"
GH_COMMENTS_FIELD = "comments"
GH_COMMENT_BODY_FIELD = "body"
GH_STATE_CLOSED = "CLOSED"
GH_VIEW_FIELDS = FIELD_LIST_SEPARATOR.join((GH_STATE_FIELD, GH_COMMENTS_FIELD))

ARGUMENT_PLAN = "--plan"
ARGUMENT_REPO_PATH = "--repo-path"
ARGUMENT_DRY_RUN = "--dry-run"
ARGUMENT_PUSH = "--push"
ARGUMENT_CREATE_PRS = "--create-prs"
ARGUMENT_ALLOW_OPTIONAL_SPLIT = "--allow-optional-split"
ARGUMENT_SUPERSEDE_SOURCE = "--supersede-source"
ARGUMENT_PRETTY = "--pretty"
ARGUMENT_STORE_TRUE_ACTION = "store_true"
DEFAULT_REPO_PATH = "."

PARSER_DESCRIPTION = "Execute an approved split-pr plan"
HELP_PLAN = "Path to approved plan JSON"
HELP_REPO_PATH = "Path inside the target git repository"
HELP_DRY_RUN = "Print planned steps without git mutations"
HELP_PUSH = "Push created branches to origin"
HELP_CREATE_PRS = "Open draft stacked PRs; implies --push"
HELP_ALLOW_OPTIONAL_SPLIT = "Execute even when the plan says the split is optional"
HELP_SUPERSEDE_SOURCE = (
    "Comment on and close source_pr_number after a full multi-slice draft "
    "stack lands (default: on when --create-prs)"
)
HELP_PRETTY = "Pretty-print JSON"

DEFAULT_COMMIT_MESSAGE_TEMPLATE = "feat: %s\n\n%s\n\nSplit from PR #%s."

DRAFT_PR_SUMMARY_HEADING = "## Summary"
DRAFT_PR_SOURCE_HEADING = "## Split source"
DRAFT_PR_SOURCE_TEMPLATE = "Excised from pull request #%s via `/split-pr`."
DRAFT_PR_DEPENDENCIES_HEADING = "## Dependencies"
DRAFT_PR_DEPENDENCIES_TEMPLATE = "Base branch: `%s`. Merge earlier slices first."
DRAFT_PR_TESTING_HEADING = "## Testing"
DRAFT_PR_TESTING_NOTE = (
    "File-partitioned from the parent pull request. Project-wide CI on this "
    "slice alone is not claimed by `/split-pr` unless verified separately."
)

ERROR_DIRTY_TREE = "working tree is dirty; commit or stash before execute_split"
ERROR_REPO_NOT_GIT = "path is not inside a git repository: %s"
ERROR_EXECUTE_FAILED = "execute_split failed: %s"
ERROR_BRANCH_EXISTS = "branch already exists: %s"
ERROR_CHECKOUT_FILES = "failed to checkout files from %s: %s"
ERROR_COMMIT_FAILED = "commit failed on %s: %s"
ERROR_PUSH_FAILED = "push failed for %s: %s"
ERROR_PR_CREATE_FAILED = "gh pr create failed for %s: %s"
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
ERROR_PLAN_MISSING_PR_IDENTITY = "plan missing pr identity (title and pr_number)"
SKIP_REASON_EMPTY_SLICE = "no_change_against_base"

NEWLINE = "\n"
EMPTY_JSON_OBJECT_TEXT = "{}"
MARKDOWN_BODY_SUFFIX = ".md"

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
