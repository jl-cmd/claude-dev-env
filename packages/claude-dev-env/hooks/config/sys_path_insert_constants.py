"""Constants for the sys.path.insert deduplication guard checker."""

MAX_SYS_PATH_INSERT_ISSUES: int = 25
SYS_PATH_INSERT_GUIDANCE: str = "guard with `if <path> not in sys.path:` to avoid pushing the same entry on every reload"
