"""Thresholds and path markers for the hand-written line PR analyzer.

::

    hand_written_lines >= 200  -> requires_split_analysis
    hand_written_lines >= 600  -> default_split (unless atomic_exception)
"""

from __future__ import annotations

SPLIT_ANALYSIS_HAND_WRITTEN_LINE_THRESHOLD: int = 200
"""Hand-written lines that require a recorded split analysis."""

DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD: int = 600
"""Hand-written lines that default to multiple PR slices."""

EXIT_CODE_SUCCESS: int = 0
EXIT_CODE_FAILURE: int = 1

JSON_INDENT_SPACES: int = 2
UTF8_ENCODING: str = "utf-8"

CHURN_CLASS_HAND_WRITTEN: str = "hand_written"
CHURN_CLASS_GENERATED: str = "generated"
CHURN_CLASS_VENDOR: str = "vendor"
CHURN_CLASS_MINIFIED: str = "minified"
CHURN_CLASS_LOCKFILE: str = "lockfile"

ALL_GENERATED_PATH_MARKERS: tuple[str, ...] = (
    "/generated/",
    ".generated.",
    "/dist/",
    "/build/",
)

ALL_VENDOR_PATH_MARKERS: tuple[str, ...] = (
    "/vendor/",
    "/third_party/",
    "/node_modules/",
)

ALL_MINIFIED_SUFFIXES: tuple[str, ...] = (
    ".min.js",
    ".min.css",
    ".min.mjs",
)

ALL_LOCKFILE_NAMES: frozenset[str] = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "Cargo.lock",
        "Pipfile.lock",
        "composer.lock",
        "Gemfile.lock",
    }
)

PAYLOAD_KEY_HAND_WRITTEN_LINES: str = "hand_written_lines"
PAYLOAD_KEY_EXCLUDED_CHURN_LINES: str = "excluded_churn_lines"
PAYLOAD_KEY_FILE_COUNT: str = "file_count"
PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS: str = "requires_split_analysis"
PAYLOAD_KEY_DEFAULT_SPLIT: str = "default_split"
PAYLOAD_KEY_ATOMIC_EXCEPTION: str = "atomic_exception"
PAYLOAD_KEY_ALL_FILES: str = "all_files"
PAYLOAD_KEY_ERROR: str = "error"
PAYLOAD_KEY_FABLE_VERDICT: str = "fable_verdict"
PAYLOAD_KEY_REASON: str = "reason"

FILE_KEY_PATH: str = "path"
FILE_KEY_ADDITIONS: str = "additions"
FILE_KEY_DELETIONS: str = "deletions"
FILE_KEY_CHURN_CLASS: str = "churn_class"
FILE_KEY_CHANGED_LINES: str = "changed_lines"

GH_COMMAND: str = "gh"
GH_PR_VIEW: str = "pr"
GH_JSON_FLAG: str = "--json"
GH_REPO_FLAG: str = "--repo"
GH_PR_JSON_FIELDS: str = "number,files"
GH_FIELD_FILES: str = "files"
GH_FILE_PATH: str = "path"
GH_FILE_ADDITIONS: str = "additions"
GH_FILE_DELETIONS: str = "deletions"
