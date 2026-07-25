"""JSON plan field names and verification messages."""

from __future__ import annotations

PLAN_KEY_PR_NUMBER = "pr_number"
PLAN_KEY_TITLE = "title"
PLAN_KEY_BASE_REF = "base_ref"
PLAN_KEY_HEAD_REF = "head_ref"
PLAN_KEY_HEAD_SHA = "head_sha"
PLAN_KEY_SOURCE_BRANCH = "source_branch"
PLAN_KEY_REPO = "repo"
PLAN_KEY_FILE_COUNT = "file_count"
PLAN_KEY_ALL_FILES = "all_files"
PLAN_KEY_PROPOSED_SLICES = "proposed_slices"
PLAN_KEY_WARNINGS = "warnings"
PLAN_KEY_FEATURE_SLUG = "feature_slug"

FILE_KEY_PATH = "path"
FILE_KEY_STATUS = "status"
FILE_KEY_ADDITIONS = "additions"
FILE_KEY_DELETIONS = "deletions"
FILE_KEY_LAYER = "layer"

SLICE_KEY_INDEX = "index"
SLICE_KEY_SLUG = "slug"
SLICE_KEY_TITLE = "title"
SLICE_KEY_STORY = "story"
SLICE_KEY_LAYER = "layer"
SLICE_KEY_FILES = "files"
SLICE_KEY_BRANCH = "branch"
SLICE_KEY_BASE = "base"
SLICE_KEY_CHANGED_LINES = "changed_lines"
SLICE_KEY_FILE_COUNT = "file_count"
SLICE_KEY_FITS_REVIEW = "fits_review"
SLICE_KEY_OVERSIZED_ATOMIC = "oversized_atomic"
SLICE_KEY_SOURCE_BRANCH = "source_branch"
SLICE_KEY_PR_URL = "pr_url"
SLICE_KEY_SKIP_REASON = "skip_reason"

FILE_STATUS_ADDED = "added"
FILE_STATUS_MODIFIED = "modified"
FILE_STATUS_REMOVED = "removed"
FILE_STATUS_RENAMED = "renamed"

VERIFY_KEY_IS_VALID = "is_valid"
VERIFY_KEY_MISSING_FILES = "missing_files"
VERIFY_KEY_DUPLICATE_FILES = "duplicate_files"
VERIFY_KEY_UNKNOWN_FILES = "unknown_files"
VERIFY_KEY_EMPTY_SLICES = "empty_slices"
VERIFY_KEY_OVERSIZED_SLICES = "oversized_slices"
VERIFY_KEY_SLICE_COUNT = "slice_count"
VERIFY_KEY_COVERED_COUNT = "covered_count"
VERIFY_KEY_SOURCE_COUNT = "source_count"
VERIFY_KEY_ERRORS = "errors"

ERROR_PLAN_PATH_REQUIRED = "plan path is required"
ERROR_PLAN_UNREADABLE = "could not read plan file: %s"
ERROR_PLAN_INVALID_JSON = "plan is not valid JSON: %s"
ERROR_PLAN_MISSING_KEY = "plan missing required key: %s"
ERROR_SLICE_MISSING_KEY = "slice %s missing required key: %s"
ERROR_SLICE_CHANGED_LINES_TYPE = "slice %s has non-numeric changed_lines: %s"
ERROR_NO_FILES = "plan has no source files under all_files"
ERROR_NO_SLICES = "plan has no proposed_slices"

ALL_REQUIRED_PLAN_KEYS = (
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_KEY_SOURCE_BRANCH,
    PLAN_KEY_BASE_REF,
    PLAN_KEY_PR_NUMBER,
    PLAN_KEY_HEAD_SHA,
)
ALL_REQUIRED_SLICE_KEYS = (SLICE_KEY_BRANCH, SLICE_KEY_BASE)
UNKNOWN_SLICE_LABEL = "?"

JSON_INDENT_SPACES = 2
PLAN_ROOT_MUST_BE_OBJECT = "root must be an object"
