"""Configuration constants for the hardcoded-user-path check in code_rules_enforcer."""

import re

HARDCODED_USER_PATH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:"
    r"[A-Za-z]:[\\/](?i:users)[\\/](?!(?i:Public|Shared|All Users)(?:[\\/]|$))[^\\/]+(?=[\\/]|$)"
    r"|(?<![A-Za-z:])/Users/(?!(?i:Shared|Public)(?:/|$))[^/]+(?=/|$)"
    r"|/home/[^/]+(?=/|$))"
)
MAX_HARDCODED_USER_PATH_ISSUES: int = 25
HARDCODED_USER_PATH_GUIDANCE: str = "use pathlib.Path.home() or os.path.expanduser('~') instead of a hardcoded user directory"
