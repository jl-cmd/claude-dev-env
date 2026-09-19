"""Constants the per-session state files and the refactor guard share.

The session-edit tracker, its stage gate, and its cleanup hook are retired.
What stays is what other modules still import: the session-id sanitize pattern
and the state-file write settings the TDD content-hash store uses, the lock
filename suffix and lock-acquire timing the state-file lock uses, and the git
executable token the refactor guard uses.
"""

from __future__ import annotations

import re

STATE_FILE_DEFAULT_SESSION_ID: str = "default"
SESSION_ID_UNSAFE_CHARACTERS_PATTERN: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_-]")

STATE_FILE_ATOMIC_WRITE_SUFFIX: str = ".tmp"
STATE_FILE_JSON_INDENT_SPACES: int = 2

SESSION_EDIT_LOCK_FILE_SUFFIX: str = ".lock"
LOCK_ACQUIRE_TIMEOUT_SECONDS: float = 5.0
LOCK_ACQUIRE_RETRY_SECONDS: float = 0.01

GIT_EXECUTABLE_TOKEN: str = "git"
