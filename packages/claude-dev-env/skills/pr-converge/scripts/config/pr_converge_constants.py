"""Configuration constants for the pr-converge skill scripts.

Path templates accept ``str.format(**kwargs)`` substitution; bugbot strings
match the literal phrasing the Cursor Bugbot reviewer emits.
"""

CURSOR_BOT_LOGIN: str = "cursor[bot]"

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

BUGBOT_RUN_TRIGGER_PHRASE: str = "bugbot run\n"

BUGBOT_RUN_TEMPFILE_SUFFIX: str = ".md"

BUGBOT_RUN_TEMPFILE_PREFIX: str = "pr-converge-bugbot-run-"

PR_CONTEXT_FIELDS: str = "number,url,headRefOid,baseRefName,headRefName,isDraft"

GH_FIELD_BODY_AT_PREFIX: str = "body=@"

GH_REPO_ARG_TEMPLATE: str = "{owner}/{repo}"
