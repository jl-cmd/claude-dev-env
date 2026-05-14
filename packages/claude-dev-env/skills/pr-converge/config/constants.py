"""Constants for the pr-converge skill.

All runtime and API constants live here. Script-specific constants
(CLI args, markdown patterns, reflow settings) stay in
``scripts/config/pr_converge_constants.py``, which imports from here.
"""

CURSOR_BOT_LOGIN = "cursor[bot]"
CURSOR_LOGIN_FILTER_SUBSTRING = "cursor"
COPILOT_REVIEWER_LOGIN = "copilot-pull-request-reviewer[bot]"
COPILOT_COMMENT_LOGIN = "Copilot"
COPILOT_REVIEWER_REQUEST_ID = COPILOT_REVIEWER_LOGIN
COPILOT_LOGIN_FILTER_SUBSTRING = "copilot"
CLAUDE_REVIEWER_LOGIN = "claude[bot]"
CLAUDE_REVIEWER_REQUEST_ID = CLAUDE_REVIEWER_LOGIN
CLAUDE_LOGIN_FILTER_SUBSTRING = "claude"

ALL_COPILOT_CLEAN_REVIEW_STATES = ("APPROVED", "COMMENTED")
ALL_COPILOT_DIRTY_REVIEW_STATES = ("CHANGES_REQUESTED",)
COPILOT_SOFT_DIRTY_REVIEW_STATE = "COMMENTED"
ALL_CLAUDE_CLEAN_REVIEW_STATES = ("APPROVED",)
ALL_CLAUDE_DIRTY_REVIEW_STATES = ("CHANGES_REQUESTED", "COMMENTED")
CLAUDE_SOFT_DIRTY_REVIEW_STATE = "COMMENTED"

BUGBOT_DIRTY_BODY_REGEX = (
    r"Cursor Bugbot has reviewed your changes and found \d+ potential issue"
)
BUGBOT_CHECK_RUN_NAME_SUBSTRING = "bugbot"
ALL_BUGBOT_CHECK_RUN_ACTIVE_STATUSES = ("queued", "in_progress")
ALL_BUGBOT_CHECK_RUN_COMPLETE_CONCLUSIONS = ("success", "neutral")
BUGBOT_RUN_TRIGGER_PHRASE = "bugbot run\n"
BUGBOT_RUN_TRIGGER_WAIT_SECONDS = 8

GH_INLINE_COMMENTS_PATH_TEMPLATE = "repos/{owner}/{repo}/pulls/{number}/comments"
GH_REVIEW_COMMENTS_PATH_TEMPLATE = (
    "repos/{owner}/{repo}/pulls/{number}/reviews/{review_id}/comments"
)
GH_REVIEWS_PATH_TEMPLATE = "repos/{owner}/{repo}/pulls/{number}/reviews"
GH_CHECK_RUNS_PATH_TEMPLATE = "repos/{owner}/{repo}/commits/{sha}/check-runs"
GH_INLINE_COMMENT_CREATE_PATH_TEMPLATE = (
    "repos/{owner}/{repo}/pulls/{number}/comments"
)
GH_INLINE_COMMENT_REPLY_PATH_TEMPLATE = (
    "repos/{owner}/{repo}/pulls/{number}/comments/{comment_id}/replies"
)
GH_ISSUE_COMMENT_CREATE_PATH_TEMPLATE = (
    "repos/{owner}/{repo}/issues/{number}/comments"
)
GH_PR_OBJECT_PATH_TEMPLATE = "repos/{owner}/{repo}/pulls/{number}"
GH_REQUESTED_REVIEWERS_PATH_TEMPLATE = (
    "repos/{owner}/{repo}/pulls/{number}/requested_reviewers"
)
GH_REQUESTED_REVIEWERS_FIELD_TEMPLATE = "reviewers[]={reviewer_id}"

CHECK_RUNS_PER_PAGE = 20
REVIEWS_PER_PAGE = 100

GRAPHQL_REVIEW_THREADS_PAGE_SIZE = 100
UNRESOLVED_THREAD_DETAIL_MAX = 5

EXIT_CODE_GH_ERROR = 2
EXIT_CODE_NOT_FOUND = 1
