"""Classification tests for hand-written vs excluded churn paths."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from categorize_files import annotate_files, classify_path_churn, sum_churn_by_class
from config.split_pr_constants import (
    CHURN_CLASS_GENERATED,
    CHURN_CLASS_HAND_WRITTEN,
    CHURN_CLASS_LOCKFILE,
    CHURN_CLASS_MINIFIED,
    CHURN_CLASS_VENDOR,
    FILE_KEY_ADDITIONS,
    FILE_KEY_DELETIONS,
    FILE_KEY_PATH,
)


def test_classify_hand_written_source_paths() -> None:
    assert classify_path_churn("packages/app/main.py") == CHURN_CLASS_HAND_WRITTEN
    assert classify_path_churn("src/components/Button.tsx") == CHURN_CLASS_HAND_WRITTEN


def test_classify_excluded_churn_classes() -> None:
    assert classify_path_churn("package-lock.json") == CHURN_CLASS_LOCKFILE
    assert classify_path_churn("vendor/lib/util.js") == CHURN_CLASS_VENDOR
    assert classify_path_churn("assets/app.min.js") == CHURN_CLASS_MINIFIED
    assert classify_path_churn("src/generated/types.ts") == CHURN_CLASS_GENERATED


def test_annotate_and_sum_separates_hand_written_from_excluded() -> None:
    all_annotated = annotate_files(
        [
            {
                FILE_KEY_PATH: "src/a.py",
                FILE_KEY_ADDITIONS: 10,
                FILE_KEY_DELETIONS: 5,
            },
            {
                FILE_KEY_PATH: "package-lock.json",
                FILE_KEY_ADDITIONS: 1000,
                FILE_KEY_DELETIONS: 0,
            },
        ]
    )
    assert sum_churn_by_class(
        all_annotated, churn_class=CHURN_CLASS_HAND_WRITTEN
    ) == 15
    assert sum_churn_by_class(all_annotated, churn_class=CHURN_CLASS_LOCKFILE) == 1000
