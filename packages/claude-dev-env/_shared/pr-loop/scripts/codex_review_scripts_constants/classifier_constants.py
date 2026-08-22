"""Named constants for the Codex down-classifier."""

from __future__ import annotations

FAILURE_CLASS_USAGE_LIMIT = "usage_limit"
FAILURE_CLASS_AUTH_FAILURE = "auth_failure"
FAILURE_CLASS_CONFIG_ERROR = "config_error"
FAILURE_CLASS_MODEL_ERROR = "model_error"
FAILURE_CLASS_UNKNOWN = "unknown"
ALL_CONFIG_ERROR_MARKERS = (
    "error loading config.toml",
    "unknown variant",
)
ALL_MODEL_ERROR_MARKERS = (
    "invalid_request_error",
    "model is not supported",
    "requires a newer version of codex",
)
ALL_USAGE_LIMIT_MARKERS = (
    "rate limit",
    "too many requests",
    "http 429",
    " (429)",
    "credits exhausted",
    "out of credits",
    "api quota",
    "usage quota",
)
ALL_AUTH_FAILURE_MARKERS = (
    "unauthorized",
    "authentication failed",
    "login required",
    "not authenticated",
)
SUCCESS_EXIT_CODE = 0
