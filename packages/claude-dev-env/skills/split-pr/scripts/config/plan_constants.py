"""Constants for split-plan records, layer order, and title normalization."""

from __future__ import annotations

PLAN_SCHEMA_VERSION: int = 1
PLAN_KEY_SCHEMA_VERSION: str = "schema_version"
PLAN_KEY_SOURCE_COMMIT: str = "source_commit"
PLAN_KEY_ALL_SLICES: str = "all_slices"
PLAN_KEY_ALL_CHANGED_PATHS: str = "all_changed_paths"
SLICE_KEY_ID: str = "id"
SLICE_KEY_TITLE: str = "title"
SLICE_KEY_LAYER: str = "layer"
SLICE_KEY_ALL_PATHS: str = "all_paths"

ALL_LAYER_ORDER: tuple[str, ...] = (
    "config",
    "backend",
    "frontend",
    "tests",
    "docs",
    "other",
)
ALL_LAYER_RANK_BY_NAME: dict[str, int] = {
    each_layer: each_index for each_index, each_layer in enumerate(ALL_LAYER_ORDER)
}
UNKNOWN_LAYER_RANK: int = len(ALL_LAYER_ORDER)

CONVENTIONAL_PREFIX_PATTERN: str = (
    r"^(?P<prefix>feat|fix|docs|chore|refactor|test|ci|perf|build|style|revert)"
    r"(?:\([^)]+\))?!?:\s*"
)
TITLE_PREFIX_SEPARATOR: str = ": "
DEFAULT_TITLE_PREFIX: str = "chore"
DEFAULT_SLICE_LAYER: str = "other"
DEFAULT_EMPTY_TITLE_REMAINDER: str = "split slice"
UTF8_ENCODING: str = "utf-8"
GH_COMMAND: str = "gh"
GH_API: str = "api"
GH_PAGINATE_FLAG: str = "--paginate"
GH_SLURP_FLAG: str = "--slurp"
GH_PULLS_FILES_PATH_TEMPLATE: str = "repos/{owner}/{repo}/pulls/{pr_number}/files"
GH_REST_FILE_FILENAME: str = "filename"
FILE_KEY_PATH: str = "path"
FILE_KEY_ADDITIONS: str = "additions"
FILE_KEY_DELETIONS: str = "deletions"
FILE_KEY_SHA: str = "sha"
EXIT_CODE_SUCCESS: int = 0
PATH_SEPARATOR: str = "/"
