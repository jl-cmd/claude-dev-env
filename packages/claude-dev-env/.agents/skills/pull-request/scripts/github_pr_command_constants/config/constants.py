"""Configuration constants for process-local GitHub pull request actions."""

import re

ACTION_COMMENT = "comment"
ACTION_CREATE = "create"
ACTION_EDIT = "edit"
ACTION_REVIEW = "review"

LINTER_ACTION_COMMENT = "pr-comment"
LINTER_ACTION_CREATE = "pr-create"
LINTER_ACTION_EDIT = "pr-edit"
LINTER_ACTION_REVIEW = "pr-review"

REVIEW_EVENT_APPROVE = "approve"
REVIEW_EVENT_COMMENT = "comment"
REVIEW_EVENT_REQUEST_CHANGES = "request-changes"
ALL_REVIEW_FLAGS_BY_EVENT: dict[str, str] = {
    REVIEW_EVENT_APPROVE: "--approve",
    REVIEW_EVENT_COMMENT: "--comment",
    REVIEW_EVENT_REQUEST_CHANGES: "--request-changes",
}

ALL_LINTER_ACTIONS_BY_COMMAND: dict[str, str] = {
    ACTION_COMMENT: LINTER_ACTION_COMMENT,
    ACTION_CREATE: LINTER_ACTION_CREATE,
    ACTION_EDIT: LINTER_ACTION_EDIT,
    ACTION_REVIEW: LINTER_ACTION_REVIEW,
}

SELECTED_ACCOUNT_ENVIRONMENT_KEY = "GITHUB_DEFAULT_ACCOUNT"

ACCOUNT_LOOKUP_FAILED_MESSAGE = "error: GitHub account lookup failed\n"
ACCOUNT_LOOKUP_EMPTY_MESSAGE = "error: GitHub account lookup returned no value\n"
ACTION_FAILED_MESSAGE = "error: GitHub action failed\n"
ACCOUNT_LOOKUP_FAILURE_EXIT_CODE = 1
PACKAGE_ROOT_PARENT_INDEX = 4
SKILLS_DIRECTORY_PARENT_INDEX = 2

ALL_GH_AUTH_SWITCH_COMMAND_HEAD: tuple[str, ...] = (
    "gh",
    "auth",
    "switch",
    "--user",
)
LEGACY_RECORD_ACTIVE_MESSAGE = "error: selected legacy state record is active\n"
LEGACY_RECORD_CHANGED_MESSAGE = "error: selected legacy state record changed\n"
LEGACY_RECORD_CONFIRMATION_MESSAGE = "error: confirm inactive legacy state\n"
LEGACY_RECORD_REJECTED_MESSAGE = "error: selected legacy state record is invalid\n"
LEGACY_RESTORE_FAILED_MESSAGE = "error: GitHub account restore failed\n"
LEGACY_RECORD_INACTIVE_CONFIRMATION_FLAG = "--confirm-inactive"
LEGACY_RECORD_ORIGINAL_ACCOUNT_KEY = "original_account"
LEGACY_RECORD_PERMISSION_MODE = 0o600
LEGACY_RECORD_STALE_AGE_SECONDS = 1800
LEGACY_RECORD_NAME_PATTERN: re.Pattern[str] = re.compile(
    r"^gh_pr_author_swap_[A-Za-z0-9_-]+\.json$"
)
RECOVERY_CLEAN_EXIT_CODE = 0
RECOVERY_FAILED_EXIT_CODE = 1
RECOVERY_REJECTED_EXIT_CODE = 2
RECOVERY_UNRESOLVED_EXIT_CODE = 3
