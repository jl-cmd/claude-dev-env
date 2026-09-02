"""Constants for the TDD-enforcer hook and its decomposed parts modules.

Centralizes the freshness window, the ancestor-walk limit, the git-tracking
and git-diff command tokens, the source-file extension sets, the join
separator, and the last-observed-hash store's filename shape and JSON keys.
"""

from __future__ import annotations

FRESHNESS_WINDOW_SECONDS: int = 600
PARENT_WALK_LIMIT: int = 10
GIT_LS_FILES_TIMEOUT_SECONDS: int = 10
GIT_DIFF_TIMEOUT_SECONDS: int = 10
GIT_EXECUTABLE_NAME: str = "git"
GIT_LS_FILES_SUBCOMMAND: str = "ls-files"
GIT_DIFF_SUBCOMMAND: str = "diff"
GIT_DIFF_QUIET_FLAG: str = "--quiet"
GIT_PATHSPEC_SEPARATOR: str = "--"
HASH_STATE_FILE_PREFIX: str = "claude-tdd-test-hashes-"
HASH_STATE_FILE_SUFFIX: str = ".json"
REPOSITORY_ROOT_DIGEST_LENGTH: int = 16
STORED_CONTENT_HASH_KEY: str = "hash"
STORED_CHANGED_AT_KEY: str = "changed_at"
PYTHON_SOURCE_EXTENSION: str = ".py"
ENTRY_HOOK_FILE_NAME: str = "tdd_enforcer.py"
NEWLINE_JOIN_SEPARATOR: str = "\n"
ALL_PRODUCTION_EXTENSIONS: frozenset[str] = frozenset({".py", ".ts", ".tsx", ".js", ".jsx"})
ALL_SKIP_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt"}
)
ALL_SKIP_NAME_PATTERNS: frozenset[str] = frozenset(
    {"test_", "_test.", ".test.", "tests/", "__tests__/", "conftest", "fixture", "mock", "stub"}
)
ALL_DIRECTORY_SKIP_COMPONENTS: frozenset[str] = frozenset(
    {"conftest", "fixture", "fixtures", "mock", "mocks", "stub", "stubs"}
)
ALL_DOTCLAUDE_PATH_SEGMENTS: frozenset[str] = frozenset({".claude"})
ALL_REPO_BOUNDARY_SENTINELS: frozenset[str] = frozenset(
    {".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"}
)
ALL_JAVASCRIPT_TEST_EXTENSIONS: frozenset[str] = frozenset({".tsx", ".ts", ".jsx", ".js"})
