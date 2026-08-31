"""Contract: source_commit and title normalization are required."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from verify_plan import verify_split_plan_coverage


def test_missing_source_commit_fails() -> None:
    plan = {
        "schema_version": 1,
        "source_commit": "",
        "all_changed_paths": ["a.py"],
        "all_slices": [
            {
                "id": "01",
                "title": "feat: a",
                "layer": "backend",
                "all_paths": ["a.py"],
            }
        ],
    }
    with pytest.raises(ValueError, match="source_commit"):
        verify_split_plan_coverage(plan)


def test_stacked_title_fails_after_build_would_have_normalized() -> None:
    plan = {
        "schema_version": 1,
        "source_commit": "abc",
        "all_changed_paths": ["a.py"],
        "all_slices": [
            {
                "id": "01",
                "title": "feat: feat: a",
                "layer": "backend",
                "all_paths": ["a.py"],
            }
        ],
    }
    with pytest.raises(ValueError, match="title"):
        verify_split_plan_coverage(plan)
