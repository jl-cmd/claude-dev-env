"""Smoke tests for revoke_project_claude_permissions wiring.

Confirms the module imports cleanly with the constants now sourced from
pr_loop_shared_constants/claude_permissions_constants.py and
pr_loop_shared_constants/claude_settings_keys_constants.py.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_revoke_module() -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    parent_directory = str(scripts_directory.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    module_path = scripts_directory / "revoke_project_claude_permissions.py"
    specification = importlib.util.spec_from_file_location(
        "revoke_project_claude_permissions", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _write_legacy_form_settings_file(
    settings_path: Path, revoke_module: ModuleType, project_path: str
) -> None:
    """Seed a settings file with only pre-#158 legacy Write()/Glob() rules.

    One Write(/.claude/**) allow rule, and a Write(/.claude/<pattern>) plus
    a Glob(/.claude/<pattern>) deny rule for every agent-config path
    pattern -- the exact stranded-rule shapes issue #233 describes."""
    legacy_allow_rule = f"Write({project_path}/.claude/**)"
    legacy_deny_rules = [
        f"Write({project_path}/.claude/{each_pattern})"
        for each_pattern in revoke_module.ALL_AGENT_CONFIG_PATH_PATTERNS
    ] + [
        f"Glob({project_path}/.claude/{each_pattern})"
        for each_pattern in revoke_module.ALL_AGENT_CONFIG_PATH_PATTERNS
    ]
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [legacy_allow_rule],
                    "deny": legacy_deny_rules,
                }
            }
        ),
        encoding="utf-8",
    )


def test_revoke_reaps_legacy_write_and_glob_rules_leaving_no_dead_structure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A revoke run reaps the legacy Write()/Glob() rules an older grant left.

    No current-form Edit/Read rule is present, so a revoke run that reaps
    only the mint set would remove nothing and leave every legacy rule
    stranded. After revoke runs, the permissions section is gone entirely,
    matching the module's "no dead structure" contract."""
    revoke_module = _load_revoke_module()
    project_directory = tmp_path / "project"
    project_directory.mkdir()
    (project_directory / ".git").mkdir()
    settings_path = tmp_path / "home" / ".claude" / "settings.json"
    project_path = str(project_directory).replace("\\", "/")
    _write_legacy_form_settings_file(settings_path, revoke_module, project_path)

    monkeypatch.setattr(
        revoke_module, "get_claude_user_settings_path", lambda: settings_path
    )
    monkeypatch.chdir(project_directory)
    revoke_module.revoke_permissions_for_current_directory()

    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "permissions" not in saved_settings


def test_module_imports_constants_from_config_modules() -> None:
    revoke_module = _load_revoke_module()
    assert revoke_module.ALL_PERMISSION_ALLOW_TOOLS == ("Edit", "Read")
    assert revoke_module.AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX == (
        "Trusted local workspace:"
    )
    assert revoke_module.CLAUDE_SETTINGS_PERMISSIONS_KEY == "permissions"


def test_revoke_module_guards_sys_path_insert_against_duplicates() -> None:
    """revoke_project_claude_permissions.py must guard its sys.path.insert with a
    membership check so re-imports under test harnesses do not push duplicate
    entries (consistent with sibling modules in the same directory)."""
    module_source = (
        Path(__file__).parent.parent / "revoke_project_claude_permissions.py"
    ).read_text(encoding="utf-8")
    assert "if parent_directory not in sys.path:" in module_source, (
        "revoke_project_claude_permissions.py must guard sys.path.insert against "
        "duplicate entries on reload (consistent with sibling modules)"
    )


def _section_of(settings: dict[str, object], section_key: str) -> dict[str, object]:
    section = settings[section_key]
    assert isinstance(section, dict)
    return section


def test_remove_values_from_list_removes_matching_strings() -> None:
    revoke_module = _load_revoke_module()
    target_list: list[object] = ["keep", "drop", 7, "drop"]
    removed_count = revoke_module.remove_values_from_list(target_list, {"drop"})
    assert removed_count == 2
    assert target_list == ["keep", 7]


def test_remove_rules_from_allow_list_removes_named_rules() -> None:
    revoke_module = _load_revoke_module()
    settings: dict[str, object] = {
        "permissions": {
            "allow": ["Edit(/proj/.claude/**)", "Read(/proj/.claude/**)"],
        },
    }
    removed_count = revoke_module.remove_rules_from_allow_list(
        settings, ["Edit(/proj/.claude/**)"]
    )
    assert removed_count == 1
    assert _section_of(settings, "permissions")["allow"] == ["Read(/proj/.claude/**)"]


def test_remove_rules_from_deny_list_removes_named_rules() -> None:
    revoke_module = _load_revoke_module()
    settings: dict[str, object] = {
        "permissions": {
            "deny": ["Edit(/proj/.claude/hooks/**)", "Read(/proj/.claude/hooks/**)"],
        },
    }
    removed_count = revoke_module.remove_rules_from_deny_list(
        settings, ["Edit(/proj/.claude/hooks/**)"]
    )
    assert removed_count == 1
    assert _section_of(settings, "permissions")["deny"] == [
        "Read(/proj/.claude/hooks/**)"
    ]


def test_remove_directory_from_additional_directories_removes_entry() -> None:
    revoke_module = _load_revoke_module()
    settings: dict[str, object] = {
        "permissions": {
            "additionalDirectories": ["/proj", "/other"],
        },
    }
    removed_count = revoke_module.remove_directory_from_additional_directories(
        settings, "/proj"
    )
    assert removed_count == 1
    assert _section_of(settings, "permissions")["additionalDirectories"] == ["/other"]


def test_remove_trust_entries_for_project_removes_every_project_entry() -> None:
    revoke_module = _load_revoke_module()
    trust_prefix = revoke_module.AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX
    project_entry_a = "Trusted local workspace: /proj/.claude/** wording A"
    project_entry_b = "Trusted local workspace: /proj/.claude/** wording B"
    other_project_entry = "Trusted local workspace: /other/.claude/** unrelated"
    settings: dict[str, object] = {
        "autoMode": {
            "environment": [project_entry_a, project_entry_b, other_project_entry],
        },
    }
    removed_count = revoke_module.remove_trust_entries_for_project(
        settings, "/proj", trust_prefix
    )
    assert removed_count == 2
    assert _section_of(settings, "autoMode")["environment"] == [other_project_entry]


def test_prune_settings_after_revoke_drops_empty_sections() -> None:
    revoke_module = _load_revoke_module()
    settings: dict[str, object] = {
        "permissions": {"allow": [], "deny": []},
        "autoMode": {"environment": []},
    }
    revoke_module.prune_settings_after_revoke(settings)
    assert "permissions" not in settings
    assert "autoMode" not in settings
