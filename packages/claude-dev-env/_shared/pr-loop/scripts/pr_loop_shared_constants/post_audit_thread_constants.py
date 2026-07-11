"""Constants for post_audit_thread.py.

Centralizes every literal the script and its tests need so the script body
contains no magic values beyond the integer literals exempt from
``check_magic_values`` (``0``, ``1``, ``-1``). Constants live here per
CODE_RULES.md §4 (Config Locations) and §3 (Reuse Constants).

All scalar constants stay narrowly typed so the consuming script and tests
can rely on ``int`` / ``str`` / ``tuple`` semantics without runtime checks.
"""

from __future__ import annotations

from pathlib import Path

SKILL_BUGTEAM: str = "bugteam"
SKILL_FINDBUGS: str = "findbugs"
SKILL_QBUG: str = "qbug"
ALL_SUPPORTED_SKILLS: tuple[str, ...] = (SKILL_BUGTEAM, SKILL_FINDBUGS, SKILL_QBUG)

STATE_CLEAN: str = "CLEAN"
STATE_DIRTY: str = "DIRTY"
ALL_SUPPORTED_STATES: tuple[str, ...] = (STATE_CLEAN, STATE_DIRTY)

SEVERITY_TAG_P0: str = "P0"
SEVERITY_TAG_P1: str = "P1"
SEVERITY_TAG_P2: str = "P2"
ALL_SUPPORTED_SEVERITY_TAGS: tuple[str, ...] = (
    SEVERITY_TAG_P0,
    SEVERITY_TAG_P1,
    SEVERITY_TAG_P2,
)

INLINE_COMMENT_SIDE_RIGHT: str = "RIGHT"
INLINE_COMMENT_SIDE_LEFT: str = "LEFT"
ALL_SUPPORTED_INLINE_COMMENT_SIDES: tuple[str, ...] = (
    INLINE_COMMENT_SIDE_RIGHT,
    INLINE_COMMENT_SIDE_LEFT,
)

GITHUB_API_BASE_URL: str = "https://api.github.com"
GITHUB_API_USER_AGENT: str = "post_audit_thread.py/1"
GITHUB_API_ACCEPT_HEADER: str = "application/vnd.github+json"
GITHUB_API_VERSION_HEADER: str = "2022-11-28"

GITHUB_REVIEW_EVENT_APPROVE: str = "APPROVE"
GITHUB_REVIEW_EVENT_REQUEST_CHANGES: str = "REQUEST_CHANGES"

HTTP_STATUS_SUCCESS_RANGE_LOW: int = 200
HTTP_STATUS_SUCCESS_RANGE_HIGH: int = 300

HTTP_AUTHORIZATION_BEARER_PREFIX: str = "Bearer "
HTTP_HEADER_AUTHORIZATION: str = "Authorization"
HTTP_HEADER_ACCEPT: str = "Accept"
HTTP_HEADER_CONTENT_TYPE: str = "Content-Type"
HTTP_HEADER_GITHUB_API_VERSION: str = "X-GitHub-Api-Version"
HTTP_HEADER_USER_AGENT: str = "User-Agent"
HTTP_METHOD_POST: str = "POST"
HTTP_REQUEST_CONTENT_TYPE: str = "application/json"
HTTP_REQUEST_TIMEOUT_SECONDS: int = 30
ERROR_RESPONSE_PREVIEW_CHARS: int = 200

MAX_RETRY_ATTEMPTS: int = 3
ALL_RETRY_BACKOFF_SECONDS: tuple[int, ...] = (1, 4, 16)

EXIT_CODE_USER_ERROR: int = 1
EXIT_CODE_RETRY_EXHAUSTED: int = 2

SHORT_SHA_LENGTH: int = 7

ALL_GH_AUTH_TOKEN_COMMAND_PARTS: tuple[str, ...] = ("gh", "auth", "token")
ALL_GH_API_USER_COMMAND_PARTS: tuple[str, ...] = ("gh", "api", "user")
ALL_GH_AUTH_STATUS_COMMAND_PARTS: tuple[str, ...] = ("gh", "auth", "status")
ALL_GH_API_COMMAND_PARTS: tuple[str, ...] = ("gh", "api")
GH_AUTH_TOKEN_USER_FLAG: str = "--user"
GH_USER_LOGIN_FIELD: str = "login"
GH_PR_USER_FIELD: str = "user"
GH_API_PR_PATH_TEMPLATE: str = "repos/{owner}/{repo}/pulls/{pr_number}"
GH_AUTH_STATUS_ACCOUNT_LINE_MARKER: str = "Logged in to github.com account"
GH_AUTH_STATUS_ACCOUNT_LINE_TOKEN_SEPARATOR: str = " "

GH_TOKEN_ENV_VAR_NAME: str = "GH_TOKEN"
GITHUB_TOKEN_ENV_VAR_NAME: str = "GITHUB_TOKEN"
ALL_GH_TOKEN_ENV_VAR_NAMES: tuple[str, ...] = (
    GH_TOKEN_ENV_VAR_NAME,
    GITHUB_TOKEN_ENV_VAR_NAME,
)
BUGTEAM_REVIEWER_ACCOUNT_ENV_VAR_NAME: str = "BUGTEAM_REVIEWER_ACCOUNT"

JSON_FIELD_PATH: str = "path"
JSON_FIELD_LINE: str = "line"
JSON_FIELD_SIDE: str = "side"
JSON_FIELD_SEVERITY: str = "severity"
JSON_FIELD_DESCRIPTION: str = "description"
JSON_FIELD_FIX_SUMMARY: str = "fix_summary"
ALL_REQUIRED_FINDING_FIELDS: tuple[str, ...] = (
    JSON_FIELD_PATH,
    JSON_FIELD_LINE,
    JSON_FIELD_SIDE,
    JSON_FIELD_SEVERITY,
    JSON_FIELD_DESCRIPTION,
    JSON_FIELD_FIX_SUMMARY,
)

REVIEW_REQUEST_FIELD_COMMIT_ID: str = "commit_id"
REVIEW_REQUEST_FIELD_BODY: str = "body"
REVIEW_REQUEST_FIELD_EVENT: str = "event"
REVIEW_REQUEST_FIELD_COMMENTS: str = "comments"

REVIEW_RESPONSE_FIELD_HTML_URL: str = "html_url"

INLINE_COMMENT_FIELD_PATH: str = "path"
INLINE_COMMENT_FIELD_LINE: str = "line"
INLINE_COMMENT_FIELD_SIDE: str = "side"
INLINE_COMMENT_FIELD_BODY: str = "body"

AUDIT_REPLY_TEMPLATE_FILENAME: str = "audit-reply-template.md"
TEMPLATE_FENCE_TOKEN: str = "```"

PLACEHOLDER_SKILL: str = "<Skill>"
PLACEHOLDER_STATE_LABEL: str = "<state_label>"
PLACEHOLDER_HEADING: str = "<heading>"
PLACEHOLDER_SUMMARY_PARAGRAPH: str = "<summary paragraph>"
PLACEHOLDER_FINDINGS_COUNT: str = "<N>"
PLACEHOLDER_P0_COUNT: str = "<P0 count>"
PLACEHOLDER_P1_COUNT: str = "<P1 count>"
PLACEHOLDER_P2_COUNT: str = "<P2 count>"
PLACEHOLDER_DETAILS_BLOCK: str = "<optional collapsed details section per finding>"

STATE_LABEL_FOR_CLEAN: str = "Clean — no findings"
STATE_LABEL_FOR_DIRTY: str = "Findings requested"
HEADING_FOR_CLEAN: str = "Audit pass clean"
HEADING_FOR_DIRTY: str = "Findings recorded as inline review comments"

SUMMARY_PARAGRAPH_CLEAN_TEMPLATE: str = (
    "The {skill_display} audit pass against commit `{short_commit}` found no "
    "findings. No inline review comments were posted; the PR carries zero "
    "unresolved threads originating from this audit pass."
)
SUMMARY_PARAGRAPH_DIRTY_TEMPLATE: str = (
    "The {skill_display} audit pass against commit `{short_commit}` surfaced "
    "{findings_count} finding(s). Each finding is posted below as an inline "
    "review comment so it becomes its own resolvable thread; the unresolved-"
    "thread gate picks them up at the next pr-converge step boundary."
)

DETAILS_BLOCK_HEADER: str = "<details>\n<summary>Finding details</summary>\n"
DETAILS_BLOCK_BULLET_TEMPLATE: str = (
    "- **[{severity}]** `{path}:{line}` — {description}"
)
DETAILS_BLOCK_FOOTER: str = "\n</details>"

INLINE_COMMENT_BODY_TEMPLATE: str = (
    "**[{severity}] {skill_display} audit finding**\n\n"
    "{description}\n\n"
    "**Suggested fix:** {fix_summary}"
)

CLI_FLAG_SKILL: str = "--skill"
CLI_FLAG_OWNER: str = "--owner"
CLI_FLAG_REPO: str = "--repo"
CLI_FLAG_PR_NUMBER: str = "--pr-number"
CLI_FLAG_COMMIT: str = "--commit"
CLI_FLAG_STATE: str = "--state"
CLI_FLAG_FINDINGS_JSON: str = "--findings-json"

REVIEWS_API_PATH_TEMPLATE: str = "/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
SINGLE_REVIEW_API_PATH_TEMPLATE: str = (
    "/repos/{owner}/{repo}/pulls/{pr_number}/reviews/{review_id}"
)
SINGLE_REVIEW_COMMENTS_API_PATH_TEMPLATE: str = (
    "/repos/{owner}/{repo}/pulls/{pr_number}/reviews/{review_id}/comments"
)

AUDIT_BODY_SKELETON_OPEN_MARKER: str = "<!-- audit-body-skeleton:start -->"
AUDIT_BODY_SKELETON_CLOSE_MARKER: str = "<!-- audit-body-skeleton:end -->"


def script_directory() -> Path:
    """Return the absolute path of the parent directory holding the consuming script.

    Returns:
        Path to ``_shared/pr-loop/scripts/`` resolved through this constants
        module's location. Callers may walk up one further level
        (``script_directory().parent``) to reach the
        ``_shared/pr-loop/`` directory where ``audit-reply-template.md`` lives.
    """
    return Path(__file__).resolve().parent.parent


def template_path() -> Path:
    """Return the absolute path to ``audit-reply-template.md``.

    Returns:
        Path object pointing to ``_shared/pr-loop/audit-reply-template.md``
        relative to this constants module. Callers read this file at runtime
        so the markdown doc remains the source of truth for the body skeleton.
    """
    return script_directory().parent / AUDIT_REPLY_TEMPLATE_FILENAME
