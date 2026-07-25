"""Constants for `.github/ci/pr_labeler.py`: GitHub API settings, the five label
axes' fixed vocabulary, the conventional-commit and test-path patterns, the
per-endpoint URL templates, and the report/environment string literals."""

import re

GITHUB_API_BASE_URL: str = "https://api.github.com"
GITHUB_API_VERSION_HEADER: str = "2022-11-28"
GITHUB_API_REQUEST_TIMEOUT_SECONDS: int = 30
PULL_REQUEST_FILES_PAGE_SIZE: int = 100

PULL_REQUEST_DETAIL_URL_TEMPLATE: str = "%s/repos/%s/pulls/%s"
ISSUE_LABELS_URL_TEMPLATE: str = "%s/repos/%s/issues/%s/labels"
ISSUE_LABEL_DELETE_URL_TEMPLATE: str = "%s/repos/%s/issues/%s/labels/%s"
PULL_REQUEST_FILES_PAGE_URL_TEMPLATE: str = "%s/repos/%s/pulls/%s/files?per_page=%s&page=%s"

CONVENTIONAL_COMMIT_PREFIX_PATTERN: re.Pattern[str] = re.compile(r"^([a-z]+)(\([^)]*\))?!?:")
ALL_TYPE_LABELS_BY_COMMIT_PREFIX: dict[str, str] = {
    "feat": "type: feature",
    "fix": "type: bug",
    "docs": "type: docs",
    "refactor": "type: refactor",
    "style": "type: refactor",
    "test": "type: test",
    "ci": "type: ci",
    "build": "type: ci",
    "chore": "type: chore",
    "revert": "type: chore",
    "perf": "type: perf",
}
ALL_TYPE_LABELS: frozenset[str] = frozenset(ALL_TYPE_LABELS_BY_COMMIT_PREFIX.values())

SIZE_LABEL_EXTRA_SMALL: str = "size: XS"
SIZE_LABEL_SMALL: str = "size: S"
SIZE_LABEL_MEDIUM: str = "size: M"
SIZE_LABEL_LARGE: str = "size: L"
SIZE_LABEL_EXTRA_LARGE: str = "size: XL"
ALL_SIZE_LABELS: frozenset[str] = frozenset(
    {
        SIZE_LABEL_EXTRA_SMALL,
        SIZE_LABEL_SMALL,
        SIZE_LABEL_MEDIUM,
        SIZE_LABEL_LARGE,
        SIZE_LABEL_EXTRA_LARGE,
    }
)

STATUS_LABEL_DRAFT: str = "status: draft"
STATUS_LABEL_NEEDS_REVIEW: str = "status: needs-review"
ALL_AUTOMATED_STATUS_LABELS: frozenset[str] = frozenset({STATUS_LABEL_DRAFT, STATUS_LABEL_NEEDS_REVIEW})
ALL_HUMAN_MANAGED_STATUS_LABELS: frozenset[str] = frozenset(
    {"status: changes-requested", "status: needs-rebase", "status: ready-to-merge"}
)

STACKED_LABEL: str = "stacked"
ALL_DEFAULT_BASE_BRANCH_NAMES: frozenset[str] = frozenset({"main", "master"})

TESTS_AREA_LABEL: str = "area: tests"
MAXIMUM_AREA_LABELS: int = 3

ALL_TEST_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)test_"),
    re.compile(r"_test\.py$"),
    re.compile(r"\.test\.mjs$"),
)

LABEL_DIFF_REPORT_LINE_SEPARATOR: str = "\n"
GITHUB_TOKEN_ENVIRONMENT_VARIABLE_NAME: str = "GITHUB_TOKEN"
