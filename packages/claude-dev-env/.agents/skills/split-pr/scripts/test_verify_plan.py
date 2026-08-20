"""verify_plan accepts full coverage and rejects gaps."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from verify_plan import main, verify_split_plan_coverage


def _full_plan() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_commit": "abc",
        "all_changed_paths": ["src/a.py", "docs/b.md"],
        "all_slices": [
            {
                "id": "01-backend",
                "title": "feat: a",
                "layer": "backend",
                "all_paths": ["src/a.py"],
            },
            {
                "id": "02-docs",
                "title": "docs: b",
                "layer": "docs",
                "all_paths": ["docs/b.md"],
            },
        ],
    }


def test_verify_accepts_full_unique_coverage() -> None:
    verify_split_plan_coverage(_full_plan())


def test_verify_rejects_missing_path() -> None:
    plan = _full_plan()
    all_slices = plan["all_slices"]
    assert isinstance(all_slices, list)
    plan["all_slices"] = [all_slices[0]]
    with pytest.raises(ValueError, match="missing"):
        verify_split_plan_coverage(plan)


def test_cli_ok_on_temp_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_full_plan()), encoding="utf-8")
    assert main(["--plan-json", str(plan_path)]) == 0
