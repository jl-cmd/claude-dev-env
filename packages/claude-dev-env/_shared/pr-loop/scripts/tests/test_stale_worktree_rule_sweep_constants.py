"""Behavioral tests for stale_worktree_rule_sweep_constants.

Confirms get_claude_worktrees_root resolves the worktrees directory under
the user's ~/.claude home, and that the rule-parsing constants carry the
literal shapes the sweep relies on.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_constants_module() -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    parent_directory = str(scripts_directory.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    module_path = (
        scripts_directory
        / "pr_loop_shared_constants"
        / "stale_worktree_rule_sweep_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "pr_loop_shared_constants.stale_worktree_rule_sweep_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_worktrees_root_resolves_under_the_user_claude_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    constants_module = _load_constants_module()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    resolved_worktrees_root = constants_module.get_claude_worktrees_root()
    assert resolved_worktrees_root == tmp_path / ".claude" / "worktrees"


def test_extract_rule_target_path_reads_the_delimited_path() -> None:
    constants_module = _load_constants_module()
    extracted_path = constants_module.extract_rule_target_path(
        "Edit(/repo/wt/.claude/**)"
    )
    assert extracted_path == "/repo/wt/.claude/**"


def test_extract_rule_target_path_returns_none_for_a_non_rule() -> None:
    constants_module = _load_constants_module()
    assert constants_module.extract_rule_target_path("not a rule") is None


def test_worktree_directory_for_rule_keeps_nested_segments_below_the_root() -> None:
    constants_module = _load_constants_module()
    worktrees_root = Path("/home/dev/.claude/worktrees")
    resolved_directory = constants_module.worktree_directory_for_rule(
        "Edit(/home/dev/.claude/worktrees/repo/feature/.claude/**)", worktrees_root
    )
    assert resolved_directory == worktrees_root / "repo" / "feature"


def test_worktree_directory_for_rule_keeps_one_segment_flat_layout() -> None:
    constants_module = _load_constants_module()
    worktrees_root = Path("/home/dev/.claude/worktrees")
    resolved_directory = constants_module.worktree_directory_for_rule(
        "Edit(/home/dev/.claude/worktrees/flat-worktree/.claude/**)", worktrees_root
    )
    assert resolved_directory == worktrees_root / "flat-worktree"


def test_worktree_directory_for_rule_returns_none_outside_the_root() -> None:
    constants_module = _load_constants_module()
    worktrees_root = Path("/home/dev/.claude/worktrees")
    resolved_directory = constants_module.worktree_directory_for_rule(
        "Edit(/home/dev/project/.claude/**)", worktrees_root
    )
    assert resolved_directory is None
