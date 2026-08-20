"""Tests for teardown_worktrees.teardown_run consuming the typed workspace."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_teardown_module() -> ModuleType:
    module_path = _SCRIPTS_DIR / "teardown_worktrees.py"
    spec = importlib.util.spec_from_file_location("teardown_worktrees", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


teardown_worktrees = _load_teardown_module()


def test_teardown_run_returns_zero_when_no_worktrees_exist(tmp_path: Path) -> None:
    """With absent worktrees, teardown_run removes nothing and reports zero,
    reading each worktree path from the typed PerPrWorkspace.worktree attribute
    rather than a dict lookup."""
    run_temp_dir = tmp_path / "run"
    run_temp_dir.mkdir()
    all_pr_entries: list[dict[str, object]] = [
        {"number": 7, "owner": "owner", "repo": "repo"},
    ]
    removed_count = teardown_worktrees.teardown_run(
        run_temp_dir=run_temp_dir,
        all_pr_entries=all_pr_entries,
    )
    assert removed_count == 0
    assert not run_temp_dir.exists()


def test_teardown_run_skips_entries_without_integer_number(tmp_path: Path) -> None:
    """A PR entry whose number is not an integer is skipped before any workspace
    resolution, so teardown_run reports zero removals and still clears the run
    temp directory."""
    run_temp_dir = tmp_path / "run"
    run_temp_dir.mkdir()
    all_pr_entries: list[dict[str, object]] = [
        {"number": "not-an-int", "owner": "owner", "repo": "repo"},
    ]
    removed_count = teardown_worktrees.teardown_run(
        run_temp_dir=run_temp_dir,
        all_pr_entries=all_pr_entries,
    )
    assert removed_count == 0
    assert not run_temp_dir.exists()
