"""Smoke tests for grant_project_claude_permissions wiring.

Confirms the module imports cleanly with the constants now sourced from
pr_loop_shared_constants/claude_permissions_constants.py and
pr_loop_shared_constants/claude_settings_keys_constants.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_grant_module() -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    parent_directory = str(scripts_directory.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    module_path = scripts_directory / "grant_project_claude_permissions.py"
    specification = importlib.util.spec_from_file_location(
        "grant_project_claude_permissions", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _nested_list_at(settings: dict[str, object], section_key: str, list_key: str) -> (
    list[object]
):
    section = settings[section_key]
    assert isinstance(section, dict)
    nested_list = section[list_key]
    assert isinstance(nested_list, list)
    return nested_list


def test_module_imports_constants_from_config_modules() -> None:
    grant_module = _load_grant_module()
    assert grant_module.ALL_PERMISSION_ALLOW_TOOLS == ("Edit", "Read")
    assert grant_module.ALL_AGENT_CONFIG_DENY_TOOLS == ("Edit", "Read")
    assert "{project_path}" in grant_module.AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE
    assert grant_module.CLAUDE_SETTINGS_PERMISSIONS_KEY == "permissions"


def test_grant_module_guards_sys_path_insert_against_duplicates() -> None:
    """grant_project_claude_permissions.py must guard its sys.path.insert with a
    membership check so re-imports under test harnesses do not push duplicate
    entries (matching the pattern used by every other module in the directory)."""
    module_source = (
        Path(__file__).parent.parent / "grant_project_claude_permissions.py"
    ).read_text(encoding="utf-8")
    assert "if parent_directory not in sys.path:" in module_source, (
        "grant_project_claude_permissions.py must guard sys.path.insert against "
        "duplicate entries on reload (consistent with sibling modules)"
    )


def test_add_rules_to_allow_list_appends_new_rules_then_skips_duplicates() -> None:
    grant_module = _load_grant_module()
    settings: dict[str, object] = {}
    new_rules = ["Edit(/proj/.claude/**)", "Read(/proj/.claude/**)"]
    first_added_count = grant_module.add_rules_to_allow_list(settings, new_rules)
    assert first_added_count == 2
    allow_list = _nested_list_at(settings, "permissions", "allow")
    assert new_rules[0] in allow_list
    assert new_rules[1] in allow_list
    second_added_count = grant_module.add_rules_to_allow_list(settings, new_rules)
    assert second_added_count == 0


def test_add_rules_to_deny_list_appends_new_rules_then_skips_duplicates() -> None:
    grant_module = _load_grant_module()
    settings: dict[str, object] = {}
    new_rules = ["Edit(/proj/.claude/hooks/**)", "Read(/proj/.claude/hooks/**)"]
    first_added_count = grant_module.add_rules_to_deny_list(settings, new_rules)
    assert first_added_count == 2
    deny_list = _nested_list_at(settings, "permissions", "deny")
    assert new_rules[0] in deny_list
    assert new_rules[1] in deny_list
    second_added_count = grant_module.add_rules_to_deny_list(settings, new_rules)
    assert second_added_count == 0


def test_add_directory_to_additional_directories_is_idempotent() -> None:
    grant_module = _load_grant_module()
    settings: dict[str, object] = {}
    project_directory = "/proj"
    first_added_count = grant_module.add_directory_to_additional_directories(
        settings, project_directory
    )
    assert first_added_count == 1
    directories = _nested_list_at(settings, "permissions", "additionalDirectories")
    assert project_directory in directories
    second_added_count = grant_module.add_directory_to_additional_directories(
        settings, project_directory
    )
    assert second_added_count == 0


def test_add_auto_mode_environment_entry_is_idempotent() -> None:
    grant_module = _load_grant_module()
    settings: dict[str, object] = {}
    entry_text = "Trusted local workspace: /proj/.claude/** current wording"
    first_added_count = grant_module.add_auto_mode_environment_entry(
        settings, entry_text
    )
    assert first_added_count == 1
    environment = _nested_list_at(settings, "autoMode", "environment")
    assert entry_text in environment
    second_added_count = grant_module.add_auto_mode_environment_entry(
        settings, entry_text
    )
    assert second_added_count == 0


def test_purge_stale_trust_entries_removes_matches_and_keeps_protected() -> None:
    grant_module = _load_grant_module()
    trust_prefix = grant_module.AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX
    stale_entry = "Trusted local workspace: /proj/.claude/** stale wording"
    protected_entry = "Trusted local workspace: /proj/.claude/** current wording"
    unrelated_entry = "Some unrelated environment hint"
    settings: dict[str, object] = {
        "autoMode": {
            "environment": [stale_entry, protected_entry, unrelated_entry],
        },
    }
    purged_count = grant_module.purge_stale_trust_entries(
        settings, "/proj", trust_prefix, protected_entry=protected_entry
    )
    assert purged_count == 1
    remaining_environment = _nested_list_at(settings, "autoMode", "environment")
    assert stale_entry not in remaining_environment
    assert protected_entry in remaining_environment
    assert unrelated_entry in remaining_environment
