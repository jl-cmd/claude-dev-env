"""Constants for the fresh-branch worktree creator.

Groups: default refs, agent detection, path layout, JSON payload keys,
exit codes, and unique-path suffix limits.
"""

from __future__ import annotations

DEFAULT_BASE_REF = "origin/main"
DEFAULT_AGENT_SLUG = "claude"
FRESH_BRANCH_AGENT_ENV_VAR = "FRESH_BRANCH_AGENT"

ALL_AGENT_DETECTION_MARKERS: tuple[tuple[str, str], ...] = (
    ("CURSOR_AGENT", "cursor"),
    ("CURSOR_TRACE_ID", "cursor"),
    ("CODEX_HOME", "codex"),
    ("CODEX_CI", "codex"),
    ("GROK_BUILD_SESSION", "grok"),
    ("CLAUDECODE", "claude"),
    ("CLAUDE_CODE_ENTRYPOINT", "claude"),
)

WINDOWS_PLATFORM_PREFIX = "win"
ALL_WINDOWS_USER_SCRATCH_PARTS = ("AppData", "Local", "Temp")
USERPROFILE_ENV_VAR = "USERPROFILE"

MAXIMUM_UNIQUE_PATH_ATTEMPTS = 100
UNIQUE_PATH_SUFFIX_START = 2

PAYLOAD_KEY_BRANCH = "branch"
PAYLOAD_KEY_WORKTREE_PATH = "worktree_path"
PAYLOAD_KEY_BASE_REF = "base_ref"
PAYLOAD_KEY_BASE_COMMIT = "base_commit"
PAYLOAD_KEY_AGENT = "agent"
PAYLOAD_KEY_REPO_ROOT = "repo_root"
PAYLOAD_KEY_ERROR = "error"

EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE = 1

GIT_COMMAND = "git"
GIT_FETCH = "fetch"
GIT_REV_PARSE = "rev-parse"
GIT_SHOW_REF = "show-ref"
GIT_WORKTREE = "worktree"
GIT_WORKTREE_ADD = "add"
GIT_BRANCH_FLAG = "-b"
GIT_VERIFY_FLAG = "--verify"
GIT_QUIET_FLAG = "--quiet"
GIT_SHOW_TOPLEVEL = "--show-toplevel"
GIT_REMOTE_PREFIX = "origin/"
GIT_REFS_REMOTES_PREFIX = "refs/remotes/"

ERROR_BRANCH_NAME_REQUIRED = "branch name is required"
ERROR_AGENT_SLUG_INVALID = "agent slug must be lowercase letters, digits, or hyphens"
ERROR_REPO_NOT_GIT = "path is not inside a git repository: %s"
ERROR_BASE_REF_MISSING = "base ref not found after fetch: %s"
ERROR_FETCH_FAILED = "git fetch failed for %s: %s"
ERROR_WORKTREE_FAILED = "git worktree add failed: %s"
ERROR_UNIQUE_PATH_EXHAUSTED = "could not allocate a unique worktree path under %s"
ERROR_BASE_COMMIT_LOOKUP = "could not resolve base commit for %s: %s"

AGENT_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
