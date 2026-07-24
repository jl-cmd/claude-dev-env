"""Behavioral tests for plan coverage verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from split_pr_scripts_constants.config.analyze_constants import (  # noqa: E402
    MAXIMUM_SLICE_CHANGED_LINES,
)
from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    FILE_KEY_ADDITIONS,
    FILE_KEY_DELETIONS,
    FILE_KEY_PATH,
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_PROPOSED_SLICES,
    SLICE_KEY_CHANGED_LINES,
    SLICE_KEY_FILES,
    SLICE_KEY_FILE_COUNT,
    SLICE_KEY_INDEX,
    SLICE_KEY_OVERSIZED_ATOMIC,
    SLICE_KEY_SLUG,
    VERIFY_KEY_DUPLICATE_FILES,
    VERIFY_KEY_IS_VALID,
    VERIFY_KEY_MISSING_FILES,
    VERIFY_KEY_OVERSIZED_SLICES,
)
from verify_plan import load_plan, verify_plan  # noqa: E402


def _plan_with(
    all_paths: list[str],
    all_slice_paths: list[list[str]],
    *,
    additions_by_path: dict[str, int] | None = None,
    slice_meta: list[dict] | None = None,
) -> dict:
    additions_by_path = additions_by_path or {}
    return {
        PLAN_KEY_ALL_FILES: [
            {
                FILE_KEY_PATH: each,
                FILE_KEY_ADDITIONS: additions_by_path.get(each, 0),
                FILE_KEY_DELETIONS: 0,
            }
            for each in all_paths
        ],
        PLAN_KEY_PROPOSED_SLICES: [
            {
                SLICE_KEY_INDEX: each_index + 1,
                SLICE_KEY_SLUG: f"s{each_index + 1}",
                SLICE_KEY_FILES: each_files,
                **(slice_meta[each_index] if slice_meta else {}),
            }
            for each_index, each_files in enumerate(all_slice_paths)
        ],
    }


def test_verify_plan_accepts_full_unique_coverage() -> None:
    plan = _plan_with(["a.ts", "b.ts"], [["a.ts"], ["b.ts"]])
    report = verify_plan(plan)
    assert report[VERIFY_KEY_IS_VALID] is True
    assert report[VERIFY_KEY_MISSING_FILES] == []


def test_verify_plan_flags_missing_file() -> None:
    plan = _plan_with(["a.ts", "b.ts"], [["a.ts"]])
    report = verify_plan(plan)
    assert report[VERIFY_KEY_IS_VALID] is False
    assert "b.ts" in report[VERIFY_KEY_MISSING_FILES]


def test_verify_plan_flags_duplicate_file() -> None:
    plan = _plan_with(["a.ts"], [["a.ts"], ["a.ts"]])
    report = verify_plan(plan)
    assert report[VERIFY_KEY_IS_VALID] is False
    assert "a.ts" in report[VERIFY_KEY_DUPLICATE_FILES]


def test_load_plan_reads_json(tmp_path: Path) -> None:
    plan = _plan_with(["x.ts"], [["x.ts"]])
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    loaded = load_plan(plan_path)
    assert loaded[PLAN_KEY_ALL_FILES][0][FILE_KEY_PATH] == "x.ts"


def test_verify_plan_rejects_multi_file_slice_over_review_budget() -> None:
    plan = _plan_with(
        ["a.py", "b.py"],
        [["a.py", "b.py"]],
        additions_by_path={
            "a.py": MAXIMUM_SLICE_CHANGED_LINES // 2 + 10,
            "b.py": MAXIMUM_SLICE_CHANGED_LINES // 2 + 10,
        },
        slice_meta=[
            {
                SLICE_KEY_FILE_COUNT: 2,
                SLICE_KEY_CHANGED_LINES: MAXIMUM_SLICE_CHANGED_LINES + 20,
            }
        ],
    )
    report = verify_plan(plan)
    assert report[VERIFY_KEY_IS_VALID] is False
    assert report[VERIFY_KEY_OVERSIZED_SLICES]


def test_verify_plan_allows_oversized_atomic_single_file() -> None:
    plan = _plan_with(
        ["huge.py"],
        [["huge.py"]],
        additions_by_path={"huge.py": MAXIMUM_SLICE_CHANGED_LINES + 80},
        slice_meta=[
            {
                SLICE_KEY_FILE_COUNT: 1,
                SLICE_KEY_CHANGED_LINES: MAXIMUM_SLICE_CHANGED_LINES + 80,
                SLICE_KEY_OVERSIZED_ATOMIC: True,
            }
        ],
    )
    report = verify_plan(plan)
    assert report[VERIFY_KEY_IS_VALID] is True
    assert report[VERIFY_KEY_OVERSIZED_SLICES] == []
