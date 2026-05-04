"""Configuration constants for the pr-converge skill scripts.

Path templates accept ``str.format(**kwargs)`` substitution; bugbot strings
match the literal phrasing the Cursor Bugbot reviewer emits.
"""

import re
from pathlib import Path

CURSOR_BOT_LOGIN: str = "cursor[bot]"

COPILOT_REVIEWER_LOGIN: str = "copilot-pull-request-reviewer[bot]"

COPILOT_REVIEWER_REQUEST_ID: str = COPILOT_REVIEWER_LOGIN

COPILOT_CLEAN_REVIEW_STATE: str = "APPROVED"

ALL_COPILOT_DIRTY_REVIEW_STATES: tuple[str, ...] = ("CHANGES_REQUESTED", "COMMENTED")

COPILOT_SOFT_DIRTY_REVIEW_STATE: str = "COMMENTED"

BUGBOT_DIRTY_BODY_REGEX: str = (
    r"Cursor Bugbot has reviewed your changes and found \d+ potential issue"
)

GH_REVIEWS_PATH_TEMPLATE: str = (
    "repos/{owner}/{repo}/pulls/{number}/reviews?per_page=100"
)

GH_INLINE_COMMENTS_PATH_TEMPLATE: str = (
    "repos/{owner}/{repo}/pulls/{number}/comments?per_page=100"
)

GH_PR_OBJECT_PATH_TEMPLATE: str = "repos/{owner}/{repo}/pulls/{number}"

GH_INLINE_COMMENT_REPLY_PATH_TEMPLATE: str = (
    "repos/{owner}/{repo}/pulls/{number}/comments/{comment_id}/replies"
)

GH_REQUESTED_REVIEWERS_PATH_TEMPLATE: str = (
    "repos/{owner}/{repo}/pulls/{number}/requested_reviewers"
)

GH_REQUESTED_REVIEWERS_FIELD_TEMPLATE: str = "reviewers[]={reviewer_id}"

BUGBOT_RUN_TRIGGER_PHRASE: str = "bugbot run\n"

BUGBOT_RUN_TEMPFILE_SUFFIX: str = ".md"

BUGBOT_RUN_TEMPFILE_PREFIX: str = "pr-converge-bugbot-run-"

PR_CONTEXT_FIELDS: str = "number,url,headRefOid,baseRefName,headRefName,isDraft"

MERGEABILITY_FIELDS: str = "mergeable,mergeStateStatus,headRefOid"

GH_FIELD_BODY_AT_PREFIX: str = "body=@"

GH_REPO_ARG_TEMPLATE: str = "{owner}/{repo}"

PR_BASE_REF_FIELDS: str = "baseRefName"

COPILOT_FOLLOWUP_BRANCH_TEMPLATE: str = "chore/copilot-followup-{parent_number}-{short_sha}"

COPILOT_FOLLOWUP_PR_TITLE_TEMPLATE: str = (
    "chore: address Copilot findings from PR #{parent_number}"
)

COPILOT_FOLLOWUP_SHORT_SHA_LENGTH: int = 8

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
