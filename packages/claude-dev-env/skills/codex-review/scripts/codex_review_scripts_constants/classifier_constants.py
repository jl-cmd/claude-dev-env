"""Named constants for the Codex down-classifier.

The classifier reads the whole captured stream — the JSONL review body as well
as stderr — so every marker is a phrase that only an error line carries. A bare
status number such as ``401`` or ``429`` is not a marker: a finding that cites
``src/api.py:401-405`` would read as an auth failure.
"""

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
    "credits",
)
ALL_AUTH_FAILURE_MARKERS = (
    "unauthorized",
    "not logged in",
    "login required",
    "codex login",
)
SUCCESS_EXIT_CODE = 0
