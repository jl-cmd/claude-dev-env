"""Constants for review-budget packing of categorized files."""

from __future__ import annotations

from config.plan_constants import ALL_LAYER_ORDER
from config.split_pr_constants import (
    DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD,
    SPLIT_ANALYSIS_HAND_WRITTEN_LINE_THRESHOLD,
)

REVIEW_BUDGET_HAND_WRITTEN_LINES: int = SPLIT_ANALYSIS_HAND_WRITTEN_LINE_THRESHOLD
HARD_CAP_HAND_WRITTEN_LINES: int = DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD
SLICE_ID_TEMPLATE: str = "{index:02d}-{layer}"
SLICE_TITLE_TEMPLATE: str = "chore: {layer} slice {index}"
(
    LAYER_CONFIG,
    LAYER_BACKEND,
    LAYER_FRONTEND,
    LAYER_TESTS,
    LAYER_DOCS,
    LAYER_OTHER,
) = ALL_LAYER_ORDER
ALL_TEST_PATH_MARKERS: tuple[str, ...] = (
    "/tests/",
    "/test/",
    "test_",
    "_test.",
    ".test.",
    ".spec.",
)
ALL_DOC_SUFFIXES: tuple[str, ...] = (".md", ".rst", ".txt")
ALL_CONFIG_BASENAMES: frozenset[str] = frozenset(
    {
        "package.json",
        "pyproject.toml",
        "setup.cfg",
        "tsconfig.json",
        ".eslintrc",
        "ruff.toml",
    }
)
ALL_CONFIG_PATH_MARKERS: tuple[str, ...] = ("/config/", "/.github/")
ALL_FRONTEND_SUFFIXES: tuple[str, ...] = (
    ".tsx",
    ".jsx",
    ".css",
    ".scss",
    ".vue",
    ".svelte",
)
ALL_BACKEND_SUFFIXES: tuple[str, ...] = (
    ".py",
    ".mjs",
    ".js",
    ".ts",
    ".go",
    ".rs",
)
EXCLUDED_CHURN_LAYER_LABEL: str = "excluded-churn"
EMPTY_HAND_WRITTEN_TITLE: str = "chore: empty hand-written set"
EMPTY_HAND_WRITTEN_SLICE_ID: str = "01-other"
