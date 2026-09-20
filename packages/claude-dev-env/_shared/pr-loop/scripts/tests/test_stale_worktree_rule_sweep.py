"""Behavioral tests for stale_worktree_rule_sweep.

Drives the real sweep functions against real temp directories and a real
temp settings file, and drives the real grant and revoke flows end to end.
A live worktree directory exists on disk; a dead worktree path does not. The
sweep keeps every rule whose worktree directory still exists and drops every
rule whose worktree directory is gone, then removes exact duplicates from
each rule array. The grant and revoke runs perform that sweep before they
save, so a run whose only effect is the sweep still persists the cleanup.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_scripts_module(module_name: str) -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    parent_directory = str(scripts_directory.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    module_path = scripts_directory / f"{module_name}.py"
    specification = importlib.util.spec_from_file_location(module_name, module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _load_sweep_module() -> ModuleType:
    return _load_scripts_module("stale_worktree_rule_sweep")


permissions_common = _load_scripts_module("_claude_permissions_common")


def _make_live_worktree_directory(worktrees_root: Path) -> Path:
    live_worktree_directory = worktrees_root / "repo" / "live-worktree"
    live_worktree_directory.mkdir(parents=True)
    return live_worktree_directory


def _allow_rule_for(worktree_directory: Path) -> str:
    return f"Edit({worktree_directory}/.claude/**)"


def _deny_rule_for(worktree_directory: Path) -> str:
    return f"Read({worktree_directory}/.claude/settings*.json)"


def _permission_list(all_settings: dict[str, object], list_key: str) -> list[object]:
    permissions_section = all_settings["permissions"]
    assert isinstance(permissions_section, dict)
    rule_list = permissions_section[list_key]
    assert isinstance(rule_list, list)
    return rule_list


def test_sweep_keeps_live_worktree_rules_and_drops_dead_ones(tmp_path: Path) -> None:
    sweep_module = _load_sweep_module()
    live_worktree_directory = _make_live_worktree_directory(tmp_path)
    dead_worktree_directory = tmp_path / "repo" / "dead-worktree"
    live_allow_rule = _allow_rule_for(live_worktree_directory)
    dead_allow_rule = _allow_rule_for(dead_worktree_directory)
    live_deny_rule = _deny_rule_for(live_worktree_directory)
    dead_deny_rule = _deny_rule_for(dead_worktree_directory)
    all_settings: dict[str, object] = {
        "permissions": {
            "allow": [live_allow_rule, dead_allow_rule],
            "deny": [live_deny_rule, dead_deny_rule],
        },
    }
    removed_count = sweep_module.sweep_and_deduplicate_permission_lists(
        all_settings, tmp_path
    )
    assert removed_count == 2
    assert _permission_list(all_settings, "allow") == [live_allow_rule]
    assert _permission_list(all_settings, "deny") == [live_deny_rule]


def test_sweep_keeps_live_flat_worktree_rules_and_drops_dead_ones(tmp_path: Path) -> None:
    sweep_module = _load_sweep_module()
    live_worktree_directory = tmp_path / "flat-live"
    live_worktree_directory.mkdir(parents=True)
    dead_worktree_directory = tmp_path / "flat-dead"
    live_allow_rule = _allow_rule_for(live_worktree_directory)
    dead_allow_rule = _allow_rule_for(dead_worktree_directory)
    all_settings: dict[str, object] = {
        "permissions": {
            "allow": [live_allow_rule, dead_allow_rule],
            "deny": [],
        },
    }
    removed_count = sweep_module.sweep_and_deduplicate_permission_lists(
        all_settings, tmp_path
    )
    assert removed_count == 1
    assert _permission_list(all_settings, "allow") == [live_allow_rule]


def test_sweep_leaves_rules_for_projects_outside_the_worktrees_root(
    tmp_path: Path,
) -> None:
    sweep_module = _load_sweep_module()
    unrelated_project_rule = "Edit(/home/developer/project/.claude/**)"
    all_settings: dict[str, object] = {
        "permissions": {"allow": [unrelated_project_rule]},
    }
    removed_count = sweep_module.sweep_and_deduplicate_permission_lists(
        all_settings, tmp_path
    )
    assert removed_count == 0
    assert _permission_list(all_settings, "allow") == [unrelated_project_rule]


def test_sweep_removes_exact_duplicate_rules(tmp_path: Path) -> None:
    sweep_module = _load_sweep_module()
    live_worktree_directory = _make_live_worktree_directory(tmp_path)
    live_allow_rule = _allow_rule_for(live_worktree_directory)
    all_settings: dict[str, object] = {
        "permissions": {"allow": [live_allow_rule, live_allow_rule]},
    }
    removed_count = sweep_module.sweep_and_deduplicate_permission_lists(
        all_settings, tmp_path
    )
    assert removed_count == 1
    assert _permission_list(all_settings, "allow") == [live_allow_rule]


def test_sweep_ignores_malformed_and_non_string_entries(tmp_path: Path) -> None:
    sweep_module = _load_sweep_module()
    malformed_entry = "not a rule at all"
    all_settings: dict[str, object] = {
        "permissions": {"allow": [malformed_entry, 7, malformed_entry]},
    }
    removed_count = sweep_module.sweep_and_deduplicate_permission_lists(
        all_settings, tmp_path
    )
    assert removed_count == 1
    assert _permission_list(all_settings, "allow") == [malformed_entry, 7]


def test_sweep_tolerates_missing_permission_sections(tmp_path: Path) -> None:
    sweep_module = _load_sweep_module()
    all_settings: dict[str, object] = {}
    removed_count = sweep_module.sweep_and_deduplicate_permission_lists(
        all_settings, tmp_path
    )
    assert removed_count == 0
    assert all_settings == {}


def test_sweep_round_trips_through_a_real_temp_settings_file(tmp_path: Path) -> None:
    sweep_module = _load_sweep_module()
    worktrees_root = tmp_path / "worktrees"
    live_worktree_directory = _make_live_worktree_directory(worktrees_root)
    dead_worktree_directory = worktrees_root / "repo" / "dead-worktree"
    live_allow_rule = _allow_rule_for(live_worktree_directory)
    dead_allow_rule = _allow_rule_for(dead_worktree_directory)
    settings_path = tmp_path / "settings.json"
    permissions_common.save_settings(
        settings_path,
        {"permissions": {"allow": [live_allow_rule, dead_allow_rule]}},
    )
    loaded_settings = permissions_common.load_settings(settings_path)
    sweep_module.sweep_and_deduplicate_permission_lists(loaded_settings, worktrees_root)
    permissions_common.save_settings(settings_path, loaded_settings)
    reloaded_settings = permissions_common.load_settings(settings_path)
    assert _permission_list(reloaded_settings, "allow") == [live_allow_rule]


def test_wrapper_resolves_worktrees_root_under_the_user_claude_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sweep_module = _load_sweep_module()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    worktrees_root = tmp_path / ".claude" / "worktrees"
    live_worktree_directory = _make_live_worktree_directory(worktrees_root)
    dead_worktree_directory = worktrees_root / "repo" / "dead-worktree"
    live_allow_rule = _allow_rule_for(live_worktree_directory)
    dead_allow_rule = _allow_rule_for(dead_worktree_directory)
    all_settings: dict[str, object] = {
        "permissions": {"allow": [live_allow_rule, dead_allow_rule]},
    }
    removed_count = sweep_module.sweep_stale_worktree_rules_from_settings(all_settings)
    assert removed_count == 1
    assert _permission_list(all_settings, "allow") == [live_allow_rule]
