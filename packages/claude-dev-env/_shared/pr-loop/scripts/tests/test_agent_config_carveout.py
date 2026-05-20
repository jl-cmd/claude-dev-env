"""Behavior tests for the agent-config carve-out and stale-trust-entry purge.

Covers two Bugbot findings on PR #467:
  - Deny rules must be written to permissions.deny so agent-config edits
    require explicit per-edit user approval.
  - Trust entries in autoMode.environment must be purged on grant
    (preventing accumulation across template revisions) and removed on
    revoke regardless of the exact template wording.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_module_from_path(module_name: str, module_path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(module_name, module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _scripts_directory() -> Path:
    return Path(__file__).parent.parent


def _load_common_module() -> ModuleType:
    scripts_directory = _scripts_directory()
    scripts_directory_str = str(scripts_directory.resolve())
    if scripts_directory_str not in sys.path:
        sys.path.insert(0, scripts_directory_str)
    return _load_module_from_path(
        "_claude_permissions_common",
        scripts_directory / "_claude_permissions_common.py",
    )


def _load_grant_module() -> ModuleType:
    scripts_directory = _scripts_directory()
    scripts_directory_str = str(scripts_directory.resolve())
    if scripts_directory_str not in sys.path:
        sys.path.insert(0, scripts_directory_str)
    return _load_module_from_path(
        "grant_project_claude_permissions",
        scripts_directory / "grant_project_claude_permissions.py",
    )


def _load_revoke_module() -> ModuleType:
    scripts_directory = _scripts_directory()
    scripts_directory_str = str(scripts_directory.resolve())
    if scripts_directory_str not in sys.path:
        sys.path.insert(0, scripts_directory_str)
    return _load_module_from_path(
        "revoke_project_claude_permissions",
        scripts_directory / "revoke_project_claude_permissions.py",
    )


def _load_constants_module() -> ModuleType:
    return _load_module_from_path(
        "pr_loop_shared_constants.claude_permissions_constants",
        _scripts_directory()
        / "pr_loop_shared_constants"
        / "claude_permissions_constants.py",
    )


def _seed_grant_then_run(
    fake_settings_path: Path,
    fake_project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    pre_existing_settings: dict[str, Any],
) -> None:
    fake_settings_path.write_text(json.dumps(pre_existing_settings), encoding="utf-8")
    grant_module = _load_grant_module()
    monkeypatch.setattr(
        grant_module,
        "get_claude_user_settings_path",
        lambda: fake_settings_path,
    )
    monkeypatch.chdir(fake_project_root)
    grant_module.grant_permissions_for_current_directory()


def _seed_revoke_then_run(
    fake_settings_path: Path,
    fake_project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    pre_existing_settings: dict[str, Any],
) -> None:
    fake_settings_path.write_text(json.dumps(pre_existing_settings), encoding="utf-8")
    revoke_module = _load_revoke_module()
    monkeypatch.setattr(
        revoke_module,
        "get_claude_user_settings_path",
        lambda: fake_settings_path,
    )
    monkeypatch.chdir(fake_project_root)
    revoke_module.revoke_permissions_for_current_directory()


def _make_fake_project(tmp_path: Path) -> Path:
    fake_project_root = tmp_path / "fake_project"
    (fake_project_root / ".claude").mkdir(parents=True)
    return fake_project_root


def _project_path_as_posix(fake_project_root: Path) -> str:
    return str(fake_project_root).replace("\\", "/")


def test_grant_writes_deny_rules_for_every_tool_and_pattern(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_project_root = _make_fake_project(tmp_path)
    fake_settings_path = tmp_path / "settings.json"
    constants_module = _load_constants_module()
    _seed_grant_then_run(
        fake_settings_path, fake_project_root, monkeypatch, pre_existing_settings={}
    )
    capsys.readouterr()
    written_settings = json.loads(fake_settings_path.read_text(encoding="utf-8"))
    deny_list = written_settings["permissions"]["deny"]
    project_path_posix = _project_path_as_posix(fake_project_root)
    for each_tool in constants_module.ALL_AGENT_CONFIG_DENY_TOOLS:
        for each_pattern in constants_module.ALL_AGENT_CONFIG_PATH_PATTERNS:
            expected_rule = f"{each_tool}({project_path_posix}/.claude/{each_pattern})"
            assert expected_rule in deny_list, (
                f"deny list missing expected rule {expected_rule!r}"
            )


def test_grant_writes_glob_deny_rules_for_every_agent_config_pattern(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Glob must be in the deny tuple so agent-config paths require approval.

    The AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE promises Edit/Write/Read/Glob
    trust EXCEPT for agent-config files. Glob deny rules are how the EXCEPT
    clause is honored for the Glob tool.
    """
    fake_project_root = _make_fake_project(tmp_path)
    fake_settings_path = tmp_path / "settings.json"
    constants_module = _load_constants_module()
    _seed_grant_then_run(
        fake_settings_path, fake_project_root, monkeypatch, pre_existing_settings={}
    )
    capsys.readouterr()
    written_settings = json.loads(fake_settings_path.read_text(encoding="utf-8"))
    deny_list = written_settings["permissions"]["deny"]
    project_path_posix = _project_path_as_posix(fake_project_root)
    assert "Glob" in constants_module.ALL_AGENT_CONFIG_DENY_TOOLS
    assert "Glob" not in constants_module.ALL_PERMISSION_ALLOW_TOOLS
    for each_pattern in constants_module.ALL_AGENT_CONFIG_PATH_PATTERNS:
        expected_glob_rule = f"Glob({project_path_posix}/.claude/{each_pattern})"
        assert expected_glob_rule in deny_list, (
            f"deny list missing expected Glob rule {expected_glob_rule!r}"
        )


def test_grant_purges_stale_trust_entries_then_writes_current_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_project_root = _make_fake_project(tmp_path)
    fake_settings_path = tmp_path / "settings.json"
    project_path_posix = _project_path_as_posix(fake_project_root)
    stale_entry_a = (
        f"Trusted local workspace: {project_path_posix}/.claude/** old wording form A"
    )
    stale_entry_b = (
        f"Trusted local workspace: {project_path_posix}/.claude/** "
        f"different earlier wording"
    )
    unrelated_entry = "Some unrelated environment hint"
    pre_existing_settings: dict[str, Any] = {
        "autoMode": {
            "environment": [stale_entry_a, stale_entry_b, unrelated_entry],
        },
    }
    _seed_grant_then_run(
        fake_settings_path,
        fake_project_root,
        monkeypatch,
        pre_existing_settings=pre_existing_settings,
    )
    captured = capsys.readouterr()
    written_settings = json.loads(fake_settings_path.read_text(encoding="utf-8"))
    environment_list = written_settings["autoMode"]["environment"]
    assert stale_entry_a not in environment_list
    assert stale_entry_b not in environment_list
    assert unrelated_entry in environment_list
    matching_trust_entries = [
        each_entry
        for each_entry in environment_list
        if isinstance(each_entry, str)
        and each_entry.startswith("Trusted local workspace:")
        and f"{project_path_posix}/.claude/**" in each_entry
    ]
    assert len(matching_trust_entries) == 1
    assert "Stale auto-mode environment entries purged" in captured.out


def test_revoke_removes_deny_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_project_root = _make_fake_project(tmp_path)
    fake_settings_path = tmp_path / "settings.json"
    common_module = _load_common_module()
    constants_module = _load_constants_module()
    project_path_posix = _project_path_as_posix(fake_project_root)
    all_deny_rules = common_module.build_agent_config_deny_rules(
        project_path_posix,
        constants_module.ALL_AGENT_CONFIG_DENY_TOOLS,
        constants_module.ALL_AGENT_CONFIG_PATH_PATTERNS,
    )
    pre_existing_settings: dict[str, Any] = {
        "permissions": {
            "deny": list(all_deny_rules),
        },
    }
    _seed_revoke_then_run(
        fake_settings_path,
        fake_project_root,
        monkeypatch,
        pre_existing_settings=pre_existing_settings,
    )
    capsys.readouterr()
    written_settings = json.loads(fake_settings_path.read_text(encoding="utf-8"))
    permissions_section = written_settings.get("permissions", {})
    remaining_deny_list = permissions_section.get("deny", [])
    for each_rule in all_deny_rules:
        assert each_rule not in remaining_deny_list


def test_revoke_removes_every_legacy_trust_entry_for_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_project_root = _make_fake_project(tmp_path)
    fake_settings_path = tmp_path / "settings.json"
    project_path_posix = _project_path_as_posix(fake_project_root)
    legacy_entry_a = (
        f"Trusted local workspace: {project_path_posix}/.claude/** template revision A"
    )
    legacy_entry_b = (
        f"Trusted local workspace: {project_path_posix}/.claude/** template revision B"
    )
    unrelated_other_project_entry = (
        "Trusted local workspace: /some/other/project/.claude/** still valid"
    )
    pre_existing_settings: dict[str, Any] = {
        "autoMode": {
            "environment": [
                legacy_entry_a,
                legacy_entry_b,
                unrelated_other_project_entry,
            ],
        },
    }
    _seed_revoke_then_run(
        fake_settings_path,
        fake_project_root,
        monkeypatch,
        pre_existing_settings=pre_existing_settings,
    )
    written_settings = json.loads(fake_settings_path.read_text(encoding="utf-8"))
    environment_list = written_settings.get("autoMode", {}).get("environment", [])
    assert legacy_entry_a not in environment_list
    assert legacy_entry_b not in environment_list
    assert unrelated_other_project_entry in environment_list


def test_template_constant_documents_agent_config_carveout() -> None:
    constants_module = _load_constants_module()
    template_text = constants_module.AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE
    assert "agent-config files always require explicit per-edit user approval" in (
        template_text
    )


def test_is_trust_entry_for_project_predicate_filters_by_prefix_and_project_path() -> (
    None
):
    common_module = _load_common_module()
    project_path_posix = "/fake/proj"
    trust_prefix = "Trusted local workspace:"
    non_string_value: object = 42
    assert (
        common_module.is_trust_entry_for_project(
            non_string_value, project_path_posix, trust_prefix
        )
        is False
    )
    wrong_prefix_entry = (
        f"Something else: {project_path_posix}/.claude/** with marker token"
    )
    assert (
        common_module.is_trust_entry_for_project(
            wrong_prefix_entry, project_path_posix, trust_prefix
        )
        is False
    )
    different_project_entry = (
        "Trusted local workspace: /other/project/.claude/** unrelated"
    )
    assert (
        common_module.is_trust_entry_for_project(
            different_project_entry, project_path_posix, trust_prefix
        )
        is False
    )
    matching_entry = (
        f"Trusted local workspace: {project_path_posix}/.claude/** any wording form"
    )
    assert (
        common_module.is_trust_entry_for_project(
            matching_entry, project_path_posix, trust_prefix
        )
        is True
    )


def test_is_trust_entry_rejects_cross_project_path_suffix_collision() -> None:
    """When the project_path is a path suffix of an unrelated entry's path,
    the predicate must reject the unrelated entry (the boundary anchor case)."""
    common_module = _load_common_module()
    short_project_path = "/projects/foo"
    trust_prefix = "Trusted local workspace:"
    longer_unrelated_path_entry = (
        "Trusted local workspace: /Users/jon/projects/foo/.claude/** unrelated path"
    )
    assert (
        common_module.is_trust_entry_for_project(
            longer_unrelated_path_entry, short_project_path, trust_prefix
        )
        is False
    )
    quoted_matching_entry = (
        f'Trusted local workspace: "{short_project_path}/.claude/**" quoted form'
    )
    assert (
        common_module.is_trust_entry_for_project(
            quoted_matching_entry, short_project_path, trust_prefix
        )
        is True
    )


def test_second_grant_is_idempotent_when_no_other_settings_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Running grant twice in a row must perform zero changes the second time.

    On the second call the existing trust entry is byte-identical to the
    freshly-formatted current entry, so purge_stale_trust_entries treats it as
    protected and does not remove it; add_auto_mode_environment_entry then
    no-ops because the entry is already present.
    """
    fake_project_root = _make_fake_project(tmp_path)
    fake_settings_path = tmp_path / "settings.json"
    _seed_grant_then_run(
        fake_settings_path, fake_project_root, monkeypatch, pre_existing_settings={}
    )
    first_run_output = capsys.readouterr()
    assert "No changes needed" not in first_run_output.out
    grant_module = _load_grant_module()
    monkeypatch.setattr(
        grant_module,
        "get_claude_user_settings_path",
        lambda: fake_settings_path,
    )
    monkeypatch.chdir(fake_project_root)
    grant_module.grant_permissions_for_current_directory()
    second_run_output = capsys.readouterr()
    assert "No changes needed; settings file left untouched." in second_run_output.out
    assert "Stale auto-mode environment entries purged" not in second_run_output.out
