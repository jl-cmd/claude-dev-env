"""Path normalization fails closed on unsafe paths."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from verify_plan import normalize_repo_path, verify_split_plan_coverage


def test_normalize_strips_dot_slash() -> None:
    assert normalize_repo_path("./src/a.py") == "src/a.py"
    assert normalize_repo_path("src\\a.py") == "src/a.py"


def test_normalize_rejects_parent_and_absolute() -> None:
    with pytest.raises(ValueError):
        normalize_repo_path("../secret")
    with pytest.raises(ValueError):
        normalize_repo_path("/etc/passwd")
    with pytest.raises(ValueError):
        normalize_repo_path("C:/Windows/system32")


def test_verify_normalizes_mixed_separators() -> None:
    plan = {
        "schema_version": 1,
        "source_commit": "abc",
        "all_changed_paths": ["src\\a.py"],
        "all_slices": [
            {
                "id": "01",
                "title": "feat: a",
                "layer": "backend",
                "all_paths": ["./src/a.py"],
            }
        ],
    }
    verify_split_plan_coverage(plan)
