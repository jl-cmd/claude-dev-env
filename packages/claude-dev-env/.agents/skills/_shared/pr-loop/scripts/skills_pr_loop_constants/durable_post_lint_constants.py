"""Configuration constants for durable GitHub post validation."""

import re

ACTION_GITHUB_MCP_POST = "github-mcp-post"
ACTION_ISSUE_COMMENT = "issue-comment"
ACTION_ISSUE_CREATE = "issue-create"
ACTION_ISSUE_EDIT = "issue-edit"
ACTION_PR_COMMENT = "pr-comment"
ACTION_PR_CREATE = "pr-create"
ACTION_PR_EDIT = "pr-edit"
ACTION_PR_REVIEW = "pr-review"

ALL_POST_ACTIONS: frozenset[str] = frozenset(
    {
        ACTION_GITHUB_MCP_POST,
        ACTION_ISSUE_COMMENT,
        ACTION_ISSUE_CREATE,
        ACTION_ISSUE_EDIT,
        ACTION_PR_COMMENT,
        ACTION_PR_CREATE,
        ACTION_PR_EDIT,
        ACTION_PR_REVIEW,
    }
)

ALL_BODY_REQUIRED_ACTIONS: frozenset[str] = frozenset(
    {
        ACTION_GITHUB_MCP_POST,
        ACTION_ISSUE_COMMENT,
        ACTION_ISSUE_CREATE,
        ACTION_ISSUE_EDIT,
        ACTION_PR_COMMENT,
        ACTION_PR_CREATE,
        ACTION_PR_REVIEW,
    }
)

ALL_PR_DESCRIPTION_ACTIONS: frozenset[str] = frozenset(
    {ACTION_PR_CREATE, ACTION_PR_EDIT}
)

ALL_TITLE_ACTIONS: frozenset[str] = frozenset({ACTION_PR_CREATE, ACTION_PR_EDIT})

ALL_CONVENTIONAL_TITLE_TYPES: tuple[str, ...] = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)

CONVENTIONAL_TITLE_PATTERN: re.Pattern[str] = re.compile(
    rf"^(?:{'|'.join(ALL_CONVENTIONAL_TITLE_TYPES)})(?:\([^)\r\n]+\))?!?: [^\s].*$"
)

ALL_REQUIRED_PR_DESCRIPTION_HEADINGS: tuple[str, ...] = (
    "Summary",
    "Description",
    "Why",
    "How",
    "Verification",
)

ALL_PATH_ANCHORED_VOLATILE_PATH_MARKERS: tuple[str, ...] = (
    ".claude-profile-a/jobs/",
    ".claude/worktrees/",
)

ALL_BARE_VOLATILE_PATH_MARKERS: tuple[str, ...] = (
    "appdata/local/temp",
    "/tmp/",
    "%temp%",
    "$env:temp",
    "$claude_job_dir",
)

BODY_FILE_ENCODING = "utf-8"
CLEAN_EXIT_CODE = 0
CONTENT_FINDING_EXIT_CODE = 1
EMPTY_BODY_CODE = "empty-body"
INPUT_ERROR_EXIT_CODE = 2
PATH_ANCHOR_CHARACTER = "/"
PATH_SEGMENT_START_CHARACTERS = "_-"

BODY_FILE_UNREADABLE_MESSAGE = "body file is not readable UTF-8 text"
BODY_REQUIRED_MESSAGE = "this action requires a body file"
BODY_MUST_NOT_BE_EMPTY_MESSAGE = "body file must contain text"
EDIT_INPUT_REQUIRED_MESSAGE = "pr-edit requires a title or body file"
INVALID_ACTION_MESSAGE = "unsupported durable post action"
INVALID_TITLE_CODE = "invalid-pr-title"
INVALID_TITLE_MESSAGE = (
    "pull request title does not use the repository Conventional Commit form"
)
MISSING_HEADING_CODE = "missing-pr-description-heading"
MISSING_HEADING_MESSAGE_TEMPLATE = "body is missing required heading: {heading}"
TITLE_NOT_ALLOWED_MESSAGE = "this action does not accept a title"
TITLE_REQUIRED_MESSAGE = "pr-create requires a title"
VOLATILE_PATH_CODE = "volatile-local-path"
VOLATILE_PATH_MESSAGE = "body contains a volatile local artifact path"
