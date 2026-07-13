"""Constants for the TDD-enforcer hook and its decomposed parts modules.

Centralizes the freshness window, the ancestor-walk limit, the git-tracking
command tokens, the source-file extension sets, and the join separator.
"""

from __future__ import annotations

FRESHNESS_WINDOW_SECONDS: int = 600
PARENT_WALK_LIMIT: int = 10
GIT_LS_FILES_TIMEOUT_SECONDS: int = 10
GIT_EXECUTABLE_NAME: str = "git"
GIT_LS_FILES_SUBCOMMAND: str = "ls-files"
GIT_PATHSPEC_SEPARATOR: str = "--"
PYTHON_SOURCE_EXTENSION: str = ".py"
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
