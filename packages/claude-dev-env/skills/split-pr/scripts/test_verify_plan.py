"""Behavioral tests for plan coverage verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    FILE_KEY_PATH,
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_PROPOSED_SLICES,
    SLICE_KEY_FILES,
    SLICE_KEY_INDEX,
    SLICE_KEY_SLUG,
    VERIFY_KEY_DUPLICATE_FILES,
    VERIFY_KEY_IS_VALID,
    VERIFY_KEY_MISSING_FILES,
)
from verify_plan import load_plan, verify_plan  # noqa: E402


def _plan_with(
    all_paths: list[str],
    all_slice_paths: list[list[str]],
) -> dict:
    return {
        PLAN_KEY_ALL_FILES: [{FILE_KEY_PATH: each} for each in all_paths],
        PLAN_KEY_PROPOSED_SLICES: [
            {
                SLICE_KEY_INDEX: each_index + 1,
                SLICE_KEY_SLUG: f"s{each_index + 1}",
                SLICE_KEY_FILES: each_files,
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
