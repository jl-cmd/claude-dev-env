"""CLI and GitHub field constants for analyze_pr.

Shared CLI, JSON, and gh names come from ``common_constants``; plan field names
come from ``plan_constants``. Every consumer imports each of those names from
its owning module, so this module holds only the analyze-specific values.
"""

from __future__ import annotations

from .common_constants import FIELD_LIST_SEPARATOR

BODY_EXCERPT_MAX_LENGTH = 400

DEFAULT_BASE_REF_NAME = "main"
BRANCH_PREFIX = "split"
BRANCH_NAME_SEPARATOR = "/"
SLUG_REPLACEMENT = "-"
MAXIMUM_FEATURE_SLUG_LENGTH = 40
MAXIMUM_SLICE_CHANGED_LINES = 400
MAXIMUM_SLICE_FILE_COUNT = 10
DEFAULT_TITLE_PREFIX = "feat"
SLICE_INDEX_ZERO_PAD = 2

GH_API = "api"
GH_PAGINATE_FLAG = "--paginate"
GH_API_SLURP_FLAG = "--slurp"
GH_PR_FILES_ENDPOINT_TEMPLATE = "repos/%s/pulls/%s/files"
GH_PR_FILES_DEFAULT_OWNER_REPO = "{owner}/{repo}"
GH_API_FILE_FILENAME = "filename"
GH_API_FILE_STATUS = "status"

GH_FIELD_NUMBER = "number"
GH_FIELD_TITLE = "title"
GH_FIELD_BASE_REF = "baseRefName"
GH_FIELD_HEAD_REF = "headRefName"
GH_FIELD_HEAD_OID = "headRefOid"
GH_FIELD_FILES = "files"
GH_FIELD_CHANGED_FILES = "changedFiles"
GH_FIELD_URL = "url"
GH_FIELD_BODY = "body"
GH_FILE_PATH = "path"
GH_FILE_ADDITIONS = "additions"
GH_FILE_DELETIONS = "deletions"

GH_PR_JSON_FIELDS = FIELD_LIST_SEPARATOR.join(
    (
        GH_FIELD_NUMBER,
        GH_FIELD_TITLE,
        GH_FIELD_BASE_REF,
        GH_FIELD_HEAD_REF,
        GH_FIELD_HEAD_OID,
        GH_FIELD_CHANGED_FILES,
        GH_FIELD_URL,
        GH_FIELD_BODY,
    )
)

ERROR_PR_NUMBER_REQUIRED = "PR number is required and must be a positive integer"
ERROR_GH_FAILED = "gh pr view failed: %s"
ERROR_GH_JSON_PARSE = "gh output is not valid JSON: %s"
ERROR_GH_FILE_STATUS_FAILED = "gh api pull files failed: %s"
ERROR_GH_FILE_STATUS_JSON = "gh api pull files output is not valid JSON: %s"
ERROR_GH_FILE_COUNT_MISMATCH = (
    "fetched %s changed files but the PR reports %s; refusing to split a "
    "truncated file list"
)
PLAN_ROOT_MUST_BE_ARRAY = "root must be an array of pages"
SPLIT_OPTIONAL_NOTE_TEMPLATE = (
    "parent already fits review budget (files=%s/%s, changed_lines=%s/%s); "
    "split is optional — continue only if the user insists"
)

WARNING_SPLIT_OPTIONAL = "parent_fits_review_budget_split_optional"
WARNING_SINGLE_LAYER = "all_files_map_to_one_layer"
WARNING_OTHER_LAYER_NONEMPTY = "uncategorized_other_layer_has_files"
WARNING_OVERSIZED_ATOMIC_SLICE = "oversized_atomic_slice"

ERROR_SLICE_EXCEEDS_REVIEW_BUDGET = (
    "slice %s exceeds review budget (files=%s/%s, changed_lines=%s/%s)"
)
