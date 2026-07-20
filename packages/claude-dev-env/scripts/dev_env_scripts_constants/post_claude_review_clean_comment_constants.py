"""Constants for the clean claude-review PR issue-comment poster.

``post_claude_review_clean_comment.py`` imports every scalar and structural
constant it needs from this module so the marker, gh argv tokens, and JSON
keys are never hardcoded twice.
"""

from __future__ import annotations

CLEAN_COMMENT_MARKER_TITLE: str = "## claude-review CLEAN"
"""Stable first-line marker that identifies a clean-pass PR issue comment."""

CLEAN_COMMENT_HEAD_LINE_TEMPLATE: str = "head_sha: {head_sha}"
"""Body line carrying the full HEAD SHA the review stamped clean."""

CLEAN_COMMENT_PROMPT_LINE_TEMPLATE: str = "prompt: {prompt}"
"""Body line carrying the locked review slash-command prompt."""

CLEAN_COMMENT_MODE_LINE_TEMPLATE: str = "mode: {mode}"
"""Body line carrying the review mode when the caller supplied one."""

CLEAN_COMMENT_SERVED_COMMAND_LINE_TEMPLATE: str = (
    "served_command: {served_command}"
)
"""Body line carrying the chain binary (or in-session token) when known."""

CLEAN_COMMENT_BODY_JOIN: str = "\n"
"""Newline used to join comment body lines."""

CLEAN_COMMENT_UNKNOWN_MODE: str = "unknown"
"""Mode label written when the caller did not supply ``--mode``."""

CLEAN_COMMENT_NULL_SERVED_COMMAND: str = "null"
"""Served-command label written when the caller did not supply one."""

GH_BINARY_NAME: str = "gh"
"""GitHub CLI executable name resolved on PATH."""

GH_PR_TOKEN: str = "pr"
"""Top-level gh token selecting the pull-request command group."""

GH_REPO_TOKEN: str = "repo"
"""Top-level gh token selecting the repository command group."""

GH_API_TOKEN: str = "api"
"""Top-level gh token selecting the REST/GraphQL API command group."""

GH_VIEW_SUBCOMMAND: str = "view"
"""gh subcommand that reads PR or repository metadata."""

GH_COMMENT_SUBCOMMAND: str = "comment"
"""gh pr subcommand that posts an issue comment on the PR."""

GH_JSON_FLAG: str = "--json"
"""gh flag that selects machine-readable JSON fields."""

GH_BODY_FILE_FLAG: str = "--body-file"
"""gh flag that reads the comment body from a file (never ``--body``)."""

GH_PAGINATE_FLAG: str = "--paginate"
"""gh api flag that walks every page of a list endpoint."""

GH_SLURP_FLAG: str = "--slurp"
"""gh api flag that wraps every paginated page in one JSON array of pages,
so a cross-page read sees the whole set instead of the last page only."""

GH_PR_VIEW_JSON_FIELDS: str = "number,url,headRefOid"
"""Comma-separated fields requested from ``gh pr view --json``."""

GH_REPO_VIEW_JSON_FIELDS: str = "nameWithOwner"
"""Comma-separated fields requested from ``gh repo view --json``."""

GH_PR_NUMBER_JSON_KEY: str = "number"
"""JSON key for the PR number on ``gh pr view``."""

GH_PR_URL_JSON_KEY: str = "url"
"""JSON key for the PR HTML URL on ``gh pr view``."""

GH_PR_HEAD_OID_JSON_KEY: str = "headRefOid"
"""JSON key for the PR head OID on ``gh pr view``."""

GH_REPO_NAME_WITH_OWNER_JSON_KEY: str = "nameWithOwner"
"""JSON key for the ``owner/repo`` slug on ``gh repo view``."""

GH_COMMENT_BODY_JSON_KEY: str = "body"
"""JSON key for the text body of an issue comment."""

ISSUE_COMMENTS_API_PATH_TEMPLATE: str = (
    "repos/{owner}/{repo}/issues/{pr_number}/comments"
)
"""REST path template listing issue comments on a pull request."""

GIT_BINARY: str = "git"
"""Executable name resolved on PATH for HEAD resolution."""

GIT_REV_PARSE_SUBCOMMAND: str = "rev-parse"
"""Git subcommand used to resolve the current HEAD SHA."""

GIT_HEAD_REF: str = "HEAD"
"""Git ref name for the current checkout tip."""

CLI_CWD_FLAG: str = "--cwd"
"""CLI flag naming the PR worktree directory."""

CLI_HEAD_SHA_FLAG: str = "--head-sha"
"""CLI flag naming the full or abbreviated HEAD SHA that was reviewed."""

CLI_MODE_FLAG: str = "--mode"
"""CLI flag naming the review mode (``chain`` or ``in_session``)."""

CLI_SERVED_COMMAND_FLAG: str = "--served-command"
"""CLI flag naming the chain binary or in-session token that served."""

CLI_DRY_RUN_FLAG: str = "--dry-run"
"""CLI flag that prints the body without posting to GitHub."""

RESULT_KEY_POSTED: str = "posted"
"""JSON result key: True when a new comment was created on the PR."""

RESULT_KEY_SKIPPED: str = "skipped"
"""JSON result key: True when an existing same-SHA comment was found."""

RESULT_KEY_DRY_RUN: str = "dry_run"
"""JSON result key: True when ``--dry-run`` prevented a post."""

RESULT_KEY_HEAD_SHA: str = "head_sha"
"""JSON result key holding the SHA the comment covers."""

RESULT_KEY_PR_NUMBER: str = "pr_number"
"""JSON result key holding the PR number, or null when unresolved."""

RESULT_KEY_MESSAGE: str = "message"
"""JSON result key holding a short human-readable outcome string."""

RESULT_KEY_BODY: str = "body"
"""JSON result key holding the comment body (dry-run and success paths)."""

UTF8_ENCODING: str = "utf-8"
"""Text encoding for subprocess output and temporary body files."""

BODY_FILE_SUFFIX: str = ".md"
"""Suffix for the temporary comment body file."""

EXIT_SUCCESS: int = 0
"""Process exit code for every soft-fail outcome (never fails the review)."""

MESSAGE_ALREADY_POSTED: str = "clean comment already exists for this HEAD"
"""Outcome message when idempotency skips a duplicate post."""

MESSAGE_POSTED: str = "clean comment posted"
"""Outcome message when ``gh pr comment`` succeeds."""

MESSAGE_DRY_RUN: str = "dry-run: body not posted"
"""Outcome message when ``--dry-run`` prints the body only."""

MESSAGE_PR_RESOLVE_FAILED: str = "could not resolve PR for worktree"
"""Outcome message when ``gh pr view`` fails or returns incomplete JSON."""

MESSAGE_HEAD_RESOLVE_FAILED: str = "could not resolve HEAD SHA"
"""Outcome message when neither ``--head-sha`` nor git HEAD is available."""

MESSAGE_LIST_COMMENTS_FAILED: str = "could not list existing PR comments"
"""Outcome message when the issue-comments API call fails."""

MESSAGE_POST_FAILED: str = "gh pr comment failed"
"""Outcome message when the post call returns non-zero."""

MESSAGE_REPO_RESOLVE_FAILED: str = "could not resolve owner/repo for worktree"
"""Outcome message when ``gh repo view`` fails or returns incomplete JSON."""

NAME_WITH_OWNER_SEGMENT_COUNT: int = 2
"""Expected slash-separated segment count in a ``owner/repo`` slug."""