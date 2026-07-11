"""Configuration constants for the pr-converge skill scripts.

Path templates accept ``str.format(**kwargs)`` substitution; bugbot strings
match the literal phrasing the Cursor Bugbot reviewer emits.

All runtime and API constants are imported from ``config.constants``.
Only script-specific constants (CLI args, markdown patterns, reflow
settings) live here.
"""

import re
from pathlib import Path

from pr_converge_skill_constants.constants import (  # noqa: F401
    ALL_BUGBOT_CHECK_RUN_ACTIVE_STATUSES,
    ALL_CLAUDE_DIRTY_REVIEW_STATES,
    ALL_COPILOT_DIRTY_REVIEW_STATES,
    ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS,
    BUGBOT_CHECK_RUN_NAME_SUBSTRING,
    BUGBOT_DIRTY_BODY_REGEX,
    BUGBOT_RUN_TRIGGER_PHRASE,
    BUGBOT_RUN_TRIGGER_WAIT_SECONDS,
    CHECK_RUNS_PER_PAGE,
    ALL_CLAUDE_CLEAN_REVIEW_STATES,
    CLAUDE_LOGIN_FILTER_SUBSTRING,
    CLAUDE_REVIEWER_LOGIN,
    CLAUDE_REVIEWER_REQUEST_ID,
    CLAUDE_SOFT_DIRTY_REVIEW_STATE,
    ALL_COPILOT_CLEAN_REVIEW_STATES,
    COPILOT_LOGIN_FILTER_SUBSTRING,
    COPILOT_REVIEWER_LOGIN,
    COPILOT_REVIEWER_REQUEST_ID,
    COPILOT_SOFT_DIRTY_REVIEW_STATE,
    CURSOR_BOT_LOGIN,
    CURSOR_LOGIN_FILTER_SUBSTRING,
    EXIT_CODE_GH_ERROR,
    EXIT_CODE_NOT_FOUND,
    GH_CHECK_RUNS_PATH_TEMPLATE,
    GH_INLINE_COMMENT_CREATE_PATH_TEMPLATE,
    GH_INLINE_COMMENTS_PATH_TEMPLATE,
    GH_ISSUE_COMMENT_CREATE_PATH_TEMPLATE,
    GH_PR_OBJECT_PATH_TEMPLATE,
    GH_REQUESTED_REVIEWERS_FIELD_TEMPLATE,
    GH_REVIEW_COMMENTS_PATH_TEMPLATE,
    GH_REVIEWS_PATH_TEMPLATE,
)

BUGBOT_RUN_TEMPFILE_SUFFIX: str = ".md"

BUGBOT_RUN_TEMPFILE_PREFIX: str = "pr-converge-bugbot-run-"

PR_CONTEXT_FIELDS: str = "number,url,headRefOid,baseRefName,headRefName,isDraft"

PR_DETACHED_HEAD_ARGS_ERROR: str = "--owner and --repo require --number; all three must be provided together for detached-HEAD PR resolution"

PR_NUMBER_ARG_FLAG: str = "--number"

PR_NUMBER_ARG_HELP: str = "PR number"

PR_OWNER_ARG_FLAG: str = "--owner"

PR_OWNER_ARG_HELP: str = "GitHub repository owner"

PR_REPO_ARG_FLAG: str = "--repo"

PR_REPO_ARG_HELP: str = "GitHub repository name"

GH_REPO_FLAG: str = "--repo"

MERGEABILITY_FIELDS: str = "mergeable,mergeStateStatus,headRefOid"

GH_FIELD_BODY_AT_PREFIX: str = "body=@"

GH_REPO_ARG_TEMPLATE: str = "{owner}/{repo}"

SKILL_REFLOW_MAXIMUM_WIDTH: int = 80

PR_CONVERGE_SKILL_PATH: Path = Path(__file__).resolve().parent.parent.parent / "SKILL.md"

MARKDOWN_CODE_FENCE_MARKER: str = "```"

YAML_FRONT_MATTER_DELIMITER: str = "---"

YAML_DESCRIPTION_PREFIX: str = "description: >-"

EXAMPLE_OPEN_TAG: str = "<example>"

EXAMPLE_CLOSE_TAG: str = "</example>"

BASH_FENCE_LANGUAGE: str = "bash"

BASH_LINE_CONTINUATION_SUFFIX: str = " \\"

BASH_CONTINUATION_INDENT: str = "  "

REFLOW_FRONT_MATTER_ERROR: str = "expected YAML front matter starting with ---"

ORDERED_MARKDOWN_LIST_PATTERN: re.Pattern[str] = re.compile(
    r"^(?P<leading_whitespace>\s*)(?P<marker>\d+\.\s)(?P<body>.*)$"
)

BULLET_MARKDOWN_LIST_PATTERN: re.Pattern[str] = re.compile(
    r"^(?P<leading_whitespace>\s*)(?P<marker>[-*]\s)(?P<body>.*)$"
)

UNFINISHED_MARKDOWN_LINK_TARGET_PATTERN: re.Pattern[str] = re.compile(r"\]\([^)]*$")

MARKDOWN_HEADING_PATTERN: re.Pattern[str] = re.compile(r"^#{1,6}\s+.+$")

MARKDOWN_REFERENCE_DEFINITION_PATTERN: re.Pattern[str] = re.compile(r"^\[[^\]]+\]:\s+\S+")

BASH_LINE_CONTINUATION_MARKER_WIDTH: int = 2

CODE_FENCE_MARKER_LENGTH: int = 3

BASH_MINIMUM_SEGMENT_WIDTH: int = 1

LONG_ROW_PREVIEW_LIMIT: int = 20
