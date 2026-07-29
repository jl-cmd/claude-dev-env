"""Behavioral tests for the shared churn budget and the review-budget packer."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from categorize_files import (  # noqa: E402
    annotate_files,
    build_slices_from_files,
    compute_churn_by_path,
)
from split_pr_scripts_constants.config.analyze_constants import (  # noqa: E402
    MAXIMUM_SLICE_CHANGED_LINES,
    MAXIMUM_SLICE_FILE_COUNT,
)
from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    SLICE_KEY_CHANGED_LINES,
    SLICE_KEY_FILES,
)

OVERSIZED_LAYER_FILE_COUNT = 25
PER_FILE_CHANGED_LINES = 60
SINGLE_OVERSIZED_FILE_LINES = 900


def build_source_files(file_count: int, changed_lines: int) -> list[dict[str, object]]:
    return [
        {
            "path": f"src/api/handler_{each_index}.ts",
            "additions": changed_lines,
            "deletions": 0,
        }
        for each_index in range(file_count)
    ]


def test_churn_sums_additions_and_deletions_per_normalized_path() -> None:
    churn_by_path = compute_churn_by_path(
        [{"path": ".\\src\\a.ts", "additions": 5, "deletions": 4}]
    )

    assert churn_by_path == {"src/a.ts": 9}


def test_churn_skips_records_that_are_not_objects() -> None:
    churn_by_path = compute_churn_by_path(["src/a.ts", {"path": "src/b.ts"}])

    assert churn_by_path == {"src/b.ts": 0}


def test_oversized_layer_packs_into_slices_inside_the_review_budget() -> None:
    all_files = annotate_files(
        build_source_files(OVERSIZED_LAYER_FILE_COUNT, PER_FILE_CHANGED_LINES)
    )

    all_slices = build_slices_from_files(all_files, "add-api", "feat")

    for each_slice in all_slices:
        assert len(each_slice[SLICE_KEY_FILES]) <= MAXIMUM_SLICE_FILE_COUNT
        assert each_slice[SLICE_KEY_CHANGED_LINES] <= MAXIMUM_SLICE_CHANGED_LINES


def test_packing_covers_every_path_exactly_once() -> None:
    all_files = annotate_files(
        build_source_files(OVERSIZED_LAYER_FILE_COUNT, PER_FILE_CHANGED_LINES)
    )

    all_slices = build_slices_from_files(all_files, "add-api", "feat")

    all_packed_paths = [
        each_path for each_slice in all_slices for each_path in each_slice[SLICE_KEY_FILES]
    ]
    assert sorted(all_packed_paths) == sorted(
        str(each_file["path"]) for each_file in all_files
    )


def test_one_file_past_the_line_budget_still_yields_one_slice() -> None:
    all_files = annotate_files(build_source_files(1, SINGLE_OVERSIZED_FILE_LINES))

    all_slices = build_slices_from_files(all_files, "add-api", "feat")

    assert len(all_slices) == 1
    assert all_slices[0][SLICE_KEY_CHANGED_LINES] == SINGLE_OVERSIZED_FILE_LINES
