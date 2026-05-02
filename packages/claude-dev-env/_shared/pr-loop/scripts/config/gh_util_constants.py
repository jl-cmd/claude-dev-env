"""Constants for gh_util.py per CODE_RULES centralized-config rule."""

DEFAULT_TIMEOUT_SECONDS: int = 30
DEFAULT_RETRIES: int = 2
DEFAULT_BACKOFF_SECONDS: float = 1.0
EXPONENTIAL_BACKOFF_BASE: int = 2
GH_TIMEOUT_RETURN_CODE: int = 124
INLINE_REVIEW_COMMENTS_PATH_TEMPLATE: str = (
    "/repos/{owner}/{repo}/pulls/{pull_number}/comments"
)

ALL_TRANSIENT_ERROR_MARKERS: tuple[str, ...] = (
    "connection reset",
    "connection refused",
    "timeout",
    "timed out",
    "temporarily unavailable",
    "502",
    "503",
    "504",
    "rate limit",
)

ALL_AUTH_ERROR_MARKERS: tuple[str, ...] = (
    "gh auth login",
    "authentication failed",
    "http 401",
    "http 403",
    "forbidden",
    "resource not accessible",
)
