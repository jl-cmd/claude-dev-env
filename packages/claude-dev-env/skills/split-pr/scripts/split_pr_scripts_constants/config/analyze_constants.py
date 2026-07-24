"""CLI and GitHub field constants for analyze_pr."""

from __future__ import annotations

EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE = 1

PAYLOAD_KEY_ERROR = "error"
JSON_INDENT_SPACES = 2
BODY_EXCERPT_MAX_LENGTH = 400

DEFAULT_BASE_REF_NAME = "main"
BRANCH_PREFIX = "split"
BRANCH_NAME_SEPARATOR = "/"
SLUG_REPLACEMENT = "-"
MAXIMUM_FEATURE_SLUG_LENGTH = 40
MINIMUM_SPLIT_FILE_COUNT = 8
DEFAULT_TITLE_PREFIX = "feat"
SLICE_INDEX_ZERO_PAD = 2

GH_COMMAND = "gh"
GH_PR_VIEW = "pr"
GH_VIEW = "view"
GH_JSON_FLAG = "--json"
GH_REPO_FLAG = "--repo"
GH_PR_JSON_FIELDS = (
    "number,title,baseRefName,headRefName,headRefOid,files,url,body"
)

GH_FIELD_NUMBER = "number"
GH_FIELD_TITLE = "title"
GH_FIELD_BASE_REF = "baseRefName"
GH_FIELD_HEAD_REF = "headRefName"
GH_FIELD_HEAD_OID = "headRefOid"
GH_FIELD_FILES = "files"
GH_FIELD_URL = "url"
GH_FIELD_BODY = "body"
GH_FILE_PATH = "path"
GH_FILE_ADDITIONS = "additions"
GH_FILE_DELETIONS = "deletions"

ERROR_PR_NUMBER_REQUIRED = "PR number is required and must be a positive integer"
ERROR_GH_FAILED = "gh pr view failed: %s"
ERROR_GH_JSON_PARSE = "gh output is not valid JSON: %s"
ERROR_CLI_ARGUMENTS = "invalid or missing command-line arguments"
ERROR_BELOW_SPLIT_THRESHOLD = (
    "PR has %s changed files (threshold %s); split is optional — continue only if the user insists"
)

WARNING_BELOW_THRESHOLD = "file_count_below_default_threshold"
WARNING_SINGLE_LAYER = "all_files_map_to_one_layer"
WARNING_OTHER_LAYER_NONEMPTY = "uncategorized_other_layer_has_files"

PLAN_BODY_EXCERPT_KEY = "body_excerpt"
PLAN_URL_KEY = "url"
PLAN_THRESHOLD_NOTE_KEY = "threshold_note"
TEST_HEAD_SHA = "test-sha"
