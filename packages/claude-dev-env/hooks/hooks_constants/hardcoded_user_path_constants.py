"""Configuration constants for the hardcoded-user-path check in code_rules_enforcer."""

import re

HARDCODED_USER_PATH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:"
    r"[A-Za-z]:[\\/]+(?i:users)[\\/]+(?!(?i:Public|Shared|All Users)(?:[\\/]|$))(?:[^\\/\r\n\"`]+(?=[\\/])|[^\\/\r\n\"'`()]+(?=[\\/\r\n\"'`()]|$))"
    r"|\\{2,}(?:[^\\/\r\n]+[\\/]+)+(?i:users)[\\/]+(?!(?i:Public|Shared|All Users)(?:[\\/]|$))(?:[^\\/\r\n\"`]+(?=[\\/])|[^\\/\r\n\"'`()]+(?=[\\/\r\n\"'`()]|$))"
    r"|(?<!:)//(?:[^\\/\r\n]+/)+(?i:users)/(?!(?i:Public|Shared|All Users)(?:/|$))(?:[^/\r\n\"`]+(?=/)|[^/\r\n\"'`()]+(?=[/\r\n\"'`()]|$))"
    r"|(?i:file):///Users/(?!(?i:Shared|Public)(?:/|$))(?:[^/\r\n\"`]+(?=/)|[^/\r\n\"'`()]+(?=[/\r\n\"'`()]|$))"
    r"|(?i:file)://(?:[^/\r\n]+/)+(?i:Users)/(?!(?i:Shared|Public)(?:/|$))(?:[^/\r\n\"`]+(?=/)|[^/\r\n\"'`()]+(?=[/\r\n\"'`()]|$))"
    r"|(?i:file):///home/(?:[^/\r\n\"`]+(?=/)|[^/\r\n\"'`()]+(?=[/\r\n\"'`()]|$))"
    r"|(?i:file)://(?:[^/\r\n]+/)+(?i:home)/(?:[^/\r\n\"`]+(?=/)|[^/\r\n\"'`()]+(?=[/\r\n\"'`()]|$))"
    r"|(?<![A-Za-z0-9._:/\-\]])/Users/(?!(?i:Shared|Public)(?:/|$))(?:[^/\r\n\"`]+(?=/)|[^/\r\n\"'`()]+(?=[/\r\n\"'`()]|$))"
    r"|(?<![A-Za-z0-9._:/\-\]])/home/(?:[^/\r\n\"`]+(?=/)|[^/\r\n\"'`()]+(?=[/\r\n\"'`()]|$)))"
)
MAX_HARDCODED_USER_PATH_ISSUES: int = 25
HARDCODED_USER_PATH_GUIDANCE: str = (
    "use pathlib.Path.home() or os.path.expanduser('~') instead of a hardcoded user directory"
)
