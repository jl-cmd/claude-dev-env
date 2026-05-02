"""Revoke the permissions previously granted by grant_project_claude_permissions.

Run from the same project root you previously granted. Removes the matching
allow rules, the additionalDirectories entry, and the autoMode environment
entry from ~/.claude/settings.json. Safe to run when no prior grant exists.
After removals, prunes any newly empty lists and their parent permissions or
autoMode sections so repeated grant/revoke cycles leave no dead structure.
"""

import sys
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from _claude_permissions_common import (  # noqa: E402
    build_permission_rules,
    exit_with_error,
    get_current_project_path,
    is_valid_project_root,
    load_settings,
    prune_empty_list_then_empty_section,
    save_settings,
)
from config.claude_permissions_constants import (  # noqa: E402
    ALL_PERMISSION_ALLOW_TOOLS,
    AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE,
    get_claude_user_settings_path,
)
from config.claude_settings_keys_constants import (  # noqa: E402
    CLAUDE_SETTINGS_ADDITIONAL_DIRECTORIES_KEY,
    CLAUDE_SETTINGS_ALLOW_KEY,
    CLAUDE_SETTINGS_AUTO_MODE_KEY,
    CLAUDE_SETTINGS_ENVIRONMENT_KEY,
    CLAUDE_SETTINGS_PERMISSIONS_KEY,
)


def remove_values_from_list(
    all_target_list: list[object], all_values_to_remove: set[str]
) -> int:
    original_length = len(all_target_list)
    all_target_list[:] = [
        each_value
        for each_value in all_target_list
        if not (isinstance(each_value, str) and each_value in all_values_to_remove)
    ]
    return original_length - len(all_target_list)


def remove_rules_from_allow_list(
    all_settings: dict[str, object], all_rules_to_remove: list[str]
) -> int:
    permissions_section = all_settings.get(CLAUDE_SETTINGS_PERMISSIONS_KEY)
    if not isinstance(permissions_section, dict):
        return 0
    existing_allow_list = permissions_section.get(CLAUDE_SETTINGS_ALLOW_KEY)
    if not isinstance(existing_allow_list, list):
        return 0
    return remove_values_from_list(existing_allow_list, set(all_rules_to_remove))


def remove_directory_from_additional_directories(
    all_settings: dict[str, object], directory_path: str
) -> int:
    permissions_section = all_settings.get(CLAUDE_SETTINGS_PERMISSIONS_KEY)
    if not isinstance(permissions_section, dict):
        return 0
    existing_directories = permissions_section.get(
        CLAUDE_SETTINGS_ADDITIONAL_DIRECTORIES_KEY
    )
    if not isinstance(existing_directories, list):
        return 0
    return remove_values_from_list(existing_directories, {directory_path})


def remove_auto_mode_environment_entry(
    all_settings: dict[str, object], entry_text: str
) -> int:
    auto_mode_section = all_settings.get(CLAUDE_SETTINGS_AUTO_MODE_KEY)
    if not isinstance(auto_mode_section, dict):
        return 0
    existing_environment = auto_mode_section.get(CLAUDE_SETTINGS_ENVIRONMENT_KEY)
    if not isinstance(existing_environment, list):
        return 0
    return remove_values_from_list(existing_environment, {entry_text})


def prune_settings_after_revoke(all_settings: dict[str, object]) -> None:
    prune_empty_list_then_empty_section(
        all_settings,
        CLAUDE_SETTINGS_PERMISSIONS_KEY,
        CLAUDE_SETTINGS_ALLOW_KEY,
    )
    prune_empty_list_then_empty_section(
        all_settings,
        CLAUDE_SETTINGS_PERMISSIONS_KEY,
        CLAUDE_SETTINGS_ADDITIONAL_DIRECTORIES_KEY,
    )
    prune_empty_list_then_empty_section(
        all_settings,
        CLAUDE_SETTINGS_AUTO_MODE_KEY,
        CLAUDE_SETTINGS_ENVIRONMENT_KEY,
    )


def revoke_permissions_for_current_directory() -> None:
    claude_user_settings_path: Path = get_claude_user_settings_path()
    project_root_path = Path.cwd()
    if not is_valid_project_root(project_root_path):
        print(
            f"ERROR: cwd {project_root_path} is not a project root "
            f"(no .git or .claude). Run from a project root.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    project_path = get_current_project_path()
    permission_rules = build_permission_rules(project_path, ALL_PERMISSION_ALLOW_TOOLS)
    environment_entry = AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE.format(
        project_path=project_path
    )
    settings = load_settings(claude_user_settings_path)
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
        print(f"Settings file: {claude_user_settings_path}")
        print("No changes to revoke; settings file left untouched.")
        return
    prune_settings_after_revoke(settings)
    save_settings(claude_user_settings_path, settings)
    print(f"Project path: {project_path}")
    print(f"Settings file: {claude_user_settings_path}")
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
