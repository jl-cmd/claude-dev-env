"""Constants for the per-session gate-skip-token store.

Holds the per-session token-file name shape, the freshness window a token lives
inside, the list key the file stores under, the field names of one stored token,
and the permission mode under which the gate may escalate a deny to an ask.
"""

from __future__ import annotations

GATE_SKIP_TOKEN_FILE_PREFIX: str = "claude-gate-skip-token-"
GATE_SKIP_TOKEN_FILE_SUFFIX: str = ".json"

GATE_SKIP_TOKEN_FRESHNESS_WINDOW_SECONDS: float = 900.0

ALL_SKIP_TOKENS_KEY: str = "pending_skip_tokens"

SKIP_TOKEN_SESSION_FIELD: str = "session"
SKIP_TOKEN_FILE_PATH_FIELD: str = "file_path"
SKIP_TOKEN_CONTENT_SHA256_FIELD: str = "content_sha256"
SKIP_TOKEN_RECORDED_AT_FIELD: str = "recorded_at"

DEFAULT_PERMISSION_MODE: str = "default"
