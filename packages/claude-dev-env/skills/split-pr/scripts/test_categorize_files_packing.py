"""Packing stays under the 200 hand-written review budget per slice."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config.packing_constants import REVIEW_BUDGET_HAND_WRITTEN_LINES
from config.split_pr_constants import (
    FILE_KEY_ADDITIONS,
    FILE_KEY_DELETIONS,
    FILE_KEY_PATH,
)
from pack_files_into_slices import infer_path_layer, pack_files_into_slices


def test_infer_path_layer_maps_tests_and_docs() -> None:
    assert infer_path_layer("packages/x/tests/test_a.py") == "tests"
    assert infer_path_layer("README.md") == "docs"
    assert infer_path_layer("src/app.py") == "backend"


def test_pack_splits_when_budget_exceeded() -> None:
    all_files = [
        {FILE_KEY_PATH: "a.py", FILE_KEY_ADDITIONS: 120, FILE_KEY_DELETIONS: 0},
        {FILE_KEY_PATH: "b.py", FILE_KEY_ADDITIONS: 120, FILE_KEY_DELETIONS: 0},
    ]
    plan = pack_files_into_slices("deadbeef", all_files)
    assert len(plan["all_slices"]) == 2
    for each_slice in plan["all_slices"]:
        assert len(each_slice["all_paths"]) == 1


def test_pack_keeps_same_layer_under_budget() -> None:
    all_files = [
        {FILE_KEY_PATH: "a.py", FILE_KEY_ADDITIONS: 40, FILE_KEY_DELETIONS: 0},
        {FILE_KEY_PATH: "b.py", FILE_KEY_ADDITIONS: 40, FILE_KEY_DELETIONS: 0},
    ]
    plan = pack_files_into_slices("deadbeef", all_files)
    assert len(plan["all_slices"]) == 1
    assert set(plan["all_slices"][0]["all_paths"]) == {"a.py", "b.py"}


def test_pack_rejects_single_file_above_hard_cap() -> None:
    all_files = [
        {
            FILE_KEY_PATH: "huge.py",
            FILE_KEY_ADDITIONS: REVIEW_BUDGET_HAND_WRITTEN_LINES * 4,
            FILE_KEY_DELETIONS: 0,
        }
    ]
    with pytest.raises(ValueError, match="hard cap"):
        pack_files_into_slices("deadbeef", all_files)
