"""Constants for the stuttering ``all_``/``ALL_`` prefix detector.

Lives under the hooks-tree ``config/`` package so module-level
UPPER_SNAKE constants satisfy the CODE_RULES "constants live in config"
requirement and share a home with the other hook-tree configuration
(``messages``, ``dynamic_stderr_handler``, ``project_paths_reader``).
"""

import re

STUTTERING_ALL_PREFIX_PATTERN: re.Pattern[str] = re.compile(
    r"^_?(?:all_){2,}|^_?(?:ALL_){2,}"
)
MAX_STUTTERING_PREFIX_ISSUES: int = 50
