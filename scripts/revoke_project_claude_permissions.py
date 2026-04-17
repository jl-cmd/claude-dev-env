"""Revoke the permissions previously granted by grant_project_claude_permissions.

Run from the same project root you previously granted. Removes the matching
allow rules, the additionalDirectories entry, and the autoMode environment
entry from ~/.claude/settings.json. Safe to run when no prior grant exists.
After removals, prunes any newly empty lists and their parent permissions or
autoMode sections so repeated grant/revoke cycles leave no dead structure.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from _claude_permissions_common import (  # noqa: E402
    build_permission_rules,
    exit_with_error,
    get_current_project_path,
    load_settings,
    prune_empty_list_then_empty_section,
    save_settings,
    AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE,
    PERMISSION_ALLOW_TOOLS,
)


CLAUDE_USER_SETTINGS_PATH: Path = Path.home() / ".claude" / "settings.json"


def remove_values_from_list(target_list: list[str], values_to_remove: set[str]) -> int:
    original_length = len(target_list)
    target_list[:] = [
        each_value for each_value in target_list if each_value not in values_to_remove
    ]
    return original_length - len(target_list)


def remove_rules_from_allow_list(
    settings: dict[str, Any], rules_to_remove: list[str]
) -> int:
    permissions_section = settings.get("permissions")
    if not isinstance(permissions_section, dict):
        return 0
    existing_allow_list = permissions_section.get("allow")
    if not isinstance(existing_allow_list, list):
        return 0
    return remove_values_from_list(existing_allow_list, set(rules_to_remove))


def remove_directory_from_additional_directories(
    settings: dict[str, Any], directory_path: str
) -> int:
    permissions_section = settings.get("permissions")
    if not isinstance(permissions_section, dict):
        return 0
    existing_directories = permissions_section.get("additionalDirectories")
    if not isinstance(existing_directories, list):
        return 0
    return remove_values_from_list(existing_directories, {directory_path})


def remove_auto_mode_environment_entry(
    settings: dict[str, Any], entry_text: str
) -> int:
    auto_mode_section = settings.get("autoMode")
    if not isinstance(auto_mode_section, dict):
        return 0
    existing_environment = auto_mode_section.get("environment")
    if not isinstance(existing_environment, list):
        return 0
    return remove_values_from_list(existing_environment, {entry_text})


def prune_settings_after_revoke(settings: dict[str, Any]) -> None:
    prune_empty_list_then_empty_section(settings, "permissions", "allow")
    prune_empty_list_then_empty_section(
        settings, "permissions", "additionalDirectories"
    )
    prune_empty_list_then_empty_section(settings, "autoMode", "environment")


def revoke_permissions_for_current_directory() -> None:
    project_path = get_current_project_path()
    permission_rules = build_permission_rules(project_path, PERMISSION_ALLOW_TOOLS)
    environment_entry = AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE.format(
        project_path=project_path
    )
    settings = load_settings(CLAUDE_USER_SETTINGS_PATH)
    rules_removed_count = remove_rules_from_allow_list(settings, permission_rules)
    directories_removed_count = remove_directory_from_additional_directories(
        settings, project_path
    )
    environment_entries_removed_count = remove_auto_mode_environment_entry(
        settings, environment_entry
    )
    total_changes_count = (
        rules_removed_count
        + directories_removed_count
        + environment_entries_removed_count
    )
    if total_changes_count == 0:
        print(f"Project path: {project_path}")
        print(f"Settings file: {CLAUDE_USER_SETTINGS_PATH}")
        print("No changes to revoke; settings file left untouched.")
        return
    prune_settings_after_revoke(settings)
    save_settings(CLAUDE_USER_SETTINGS_PATH, settings)
    print(f"Project path: {project_path}")
    print(f"Settings file: {CLAUDE_USER_SETTINGS_PATH}")
    print(f"Allow rules removed: {rules_removed_count} of {len(permission_rules)}")
    print(f"Additional directories removed: {directories_removed_count}")
    print(
        f"Auto-mode environment entries removed: {environment_entries_removed_count}"
    )


if __name__ == "__main__":
    try:
        revoke_permissions_for_current_directory()
    except ValueError as path_error:
        exit_with_error(str(path_error))
