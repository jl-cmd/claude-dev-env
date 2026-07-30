"""Split-plan schema validation rejects unassigned paths."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from split_pr_script_types import build_split_plan, validate_split_plan


def test_build_and_validate_full_assignment() -> None:
    plan = build_split_plan(
        source_commit="abc123",
        all_changed_paths=["a.py", "b.md"],
        all_slices=[
            {
                "id": "01-config",
                "title": "feat: feat: config",
                "layer": "config",
                "all_paths": ["a.py"],
            },
            {
                "id": "02-docs",
                "title": "docs only",
                "layer": "docs",
                "all_paths": ["b.md"],
            },
        ],
    )
    validate_split_plan(plan)
    assert plan["schema_version"] == 1
    assert plan["all_slices"][0]["title"] == "feat: config"
    assert plan["all_slices"][1]["title"] == "chore: docs only"


def test_validate_rejects_unassigned_path() -> None:
    plan = build_split_plan(
        source_commit="abc123",
        all_changed_paths=["a.py", "orphan.py"],
        all_slices=[
            {
                "id": "01",
                "title": "feat: only a",
                "layer": "backend",
                "all_paths": ["a.py"],
            }
        ],
    )
    with pytest.raises(ValueError, match="missing"):
        validate_split_plan(plan)
