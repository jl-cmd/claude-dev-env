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
    "quota",
    "too many requests",
    "429",
    "credits",
)
ALL_AUTH_FAILURE_MARKERS = (
    "401",
    "unauthorized",
    "login",
)
SUCCESS_EXIT_CODE = 0
