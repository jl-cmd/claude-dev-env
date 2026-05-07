"""Constants for review posting and verification logic."""

EXIT_OK: int = 0
EXIT_NO_REVIEW: int = 1
EXIT_WRONG_COMMIT: int = 2
EXIT_DUPLICATE_REVIEW: int = 3
EXIT_FETCH_FAILED: int = 4

REVIEWS_PATH_TEMPLATE: str = "/repos/{owner}/{repo}/pulls/{pull_number}/reviews?per_page=100"

REVIEW_API_TIMEOUT_SECONDS: int = 120

LOOP_AUDIT_HEADER_TEMPLATE: str = "## Loop {loop_number} Audit"
BUGTEAM_LOOP_HEADER_TEMPLATE: str = "## /bugteam loop {loop_number} "

REVIEW_POST_ENDPOINT_TEMPLATE: str = (
    "/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
)

REVIEW_COMMENTS_ENDPOINT_TEMPLATE: str = (
    "/repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/comments?per_page=100"
)

REVIEW_EVENT_COMMENT: str = "COMMENT"
REVIEW_COMMENTS_SIDE: str = "RIGHT"

STATUS_OK: str = "ok"

COMMENTS_FETCH_STATUS_OK: str = "ok"
COMMENTS_FETCH_STATUS_FAILED: str = "failed"

ALL_EVENTUAL_CONSISTENCY_RETRY_DELAYS: tuple[float, ...] = (0.5, 1.0, 2.0)

MISSING_STRING_FIELD: str = ""
