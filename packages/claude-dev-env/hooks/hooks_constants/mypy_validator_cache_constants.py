"""Cache paths and tunables for the mypy_validator per-session caches.

The validator keeps two per-session caches so a Write/Edit burst under one
project root does not repeat work whose result has not changed: a config-walk
cache keyed by the target file's directory, and a content-hash cache keyed by
target file.
Both live as JSON files under the per-session hook-state cache directory the
live tree already uses for hook state. A cold or missing cache simply does the
work, so these paths are safe to miss.
"""

from __future__ import annotations

import os

__all__ = [
    "HOOK_STATE_CACHE_DIRECTORY",
    "MYPY_CONFIG_CACHE_FILENAME",
    "MYPY_CONTENT_HASH_CACHE_FILENAME",
    "SESSION_ID_ENVIRONMENT_VARIABLE",
    "UNKNOWN_SESSION_IDENTIFIER",
    "CONTENT_HASH_CACHE_PASSING_EXIT_CODE",
    "CACHE_FILE_ENCODING",
]

HOOK_STATE_CACHE_DIRECTORY = os.path.join(os.path.expanduser("~"), ".claude", "cache")

MYPY_CONFIG_CACHE_FILENAME = "mypy-validator-config-cache.json"
MYPY_CONTENT_HASH_CACHE_FILENAME = "mypy-validator-content-hash-cache.json"

SESSION_ID_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_SESSION_ID"
UNKNOWN_SESSION_IDENTIFIER = "unknown-session"

CONTENT_HASH_CACHE_PASSING_EXIT_CODE = 0

CACHE_FILE_ENCODING = "utf-8"
