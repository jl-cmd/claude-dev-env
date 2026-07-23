"""Constants for review_tier_constants."""

DEFAULT_BRANCH_FALLBACK = "main"
GIT_HEAD_REF = "HEAD"
REMOTE_HEAD_REF = "refs/remotes/origin/HEAD"
MAX_AXIS_VALUE = 2
MIN_NONEMPTY_RISK = 1
GIT_COMMAND_FAILED = "GIT_COMMAND_FAILED"
INVALID_BASE_REF = "INVALID_BASE_REF"
AMBIGUOUS_BASE_REF = "AMBIGUOUS_BASE_REF"
MALFORMED_TIER_POLICY = "MALFORMED_TIER_POLICY"
UNKNOWN_TIER = "UNKNOWN_TIER"
UNAPPROVED_TIER_DOWNGRADE = "UNAPPROVED_TIER_DOWNGRADE"
ALL_TIER_ORDER = ("T1", "T2", "T3")
ALL_PUBLIC_API_MARKERS = ("__init__.py", "api.py", "cli.py", "SKILL.md")
ALL_DEPENDENCY_MARKERS = ("package.json", "requirements", "pyproject.toml", "poetry.lock")
ALL_HARD_TRIGGER_MARKERS = {"security": ("security", "auth", "permission"), "migration": ("migration", "migrations"), "public-api": ("api.py", "__init__.py"), "release": ("release", "version")}
ALL_STATUS_DOMAINS = ("staged", "unstaged", "untracked")
JSON_INDENT = 2
ALL_STATUS_ARGUMENTS = ("status", "--porcelain=v1", "-z", "--untracked-files=all")
ROOT_PACKAGE = "."
STATUS_PREFIX_LENGTH = 3
STATUS_CODE_LENGTH = 2
ALL_PACKAGE_ROOT_NAMES = ("packages", "apps", "libs", "services")
PATH_SEPARATOR = "/"
ALL_SOURCE_SUFFIXES = (".py", ".js", ".ts")
ALL_UNTRACKED_ARGUMENTS = ("ls-files", "--others", "--exclude-standard", "-z")
ROUTING_STATE_ROOT_TRACKED = "ROUTING_STATE_ROOT_TRACKED"
PLUGIN_DATA_ENVIRONMENT = "CLAUDE_PLUGIN_DATA"
