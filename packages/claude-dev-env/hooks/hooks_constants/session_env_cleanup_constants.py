"""Configuration constants for the session_env_cleanup SessionStart hook."""

from __future__ import annotations

import os
import re

SESSION_ENV_DIRECTORY = os.path.join(os.path.expanduser("~"), ".claude", "session-env")

SECONDS_PER_DAY = 24 * 60 * 60
STALE_AGE_DAYS = 7
STALE_AGE_SECONDS = STALE_AGE_DAYS * SECONDS_PER_DAY

ALL_RMTREE_ONEXC_PYTHON_VERSION_PARTS: tuple[int, int] = (3, 12)

SESSION_ID_PAYLOAD_KEY: str = "session_id"

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

WINDOWS_PLATFORM_TAG = "win32"
