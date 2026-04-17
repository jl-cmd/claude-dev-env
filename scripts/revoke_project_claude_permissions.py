"""Revoke the permissions previously granted by grant_project_claude_permissions.

Run from the same project root you previously granted. Removes the matching
allow rules, the additionalDirectories entry, and the autoMode environment
entry from ~/.claude/settings.json. Safe to run when no prior grant exists.
"""

import json
from pathlib import Path
from typing import Any


CLAUDE_USER_SETTINGS_PATH: Path = Path.home() / ".claude" / "settings.json"
PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")
AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    "Trusted local workspace: {project_path}/.claude/** is the user's "
    "project Claude Code config tree; edits inside are routine"
)
JSON_INDENT_SPACES: int = 2


def get_current_project_path() -> str:
    return str(Path.cwd()).replace("\\", "/")


def build_permission_rule(tool_name: str, project_path: str) -> str:
    return f"{tool_name}({project_path}/.claude/**)"


def build_permission_rules(project_path: str) -> list[str]:
    return [
        build_permission_rule(each_tool, project_path)
        for each_tool in PERMISSION_ALLOW_TOOLS
    ]


def load_settings(settings_path: Path) -> dict[str, Any]:
    if not settings_path.exists():
        return {}
    return json.loads(settings_path.read_text(encoding="utf-8"))


def save_settings(settings_path: Path, settings: dict[str, Any]) -> None:
    settings_path.write_text(
        json.dumps(settings, indent=JSON_INDENT_SPACES), encoding="utf-8"
    )


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


def revoke_permissions_for_current_directory() -> None:
    project_path = get_current_project_path()
    permission_rules = build_permission_rules(project_path)
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
    save_settings(CLAUDE_USER_SETTINGS_PATH, settings)
    print(f"Project path: {project_path}")
    print(f"Settings file: {CLAUDE_USER_SETTINGS_PATH}")
    print(f"Allow rules removed: {rules_removed_count} of {len(permission_rules)}")
    print(f"Additional directories removed: {directories_removed_count}")
    print(f"Auto-mode environment entries removed: {environment_entries_removed_count}")


if __name__ == "__main__":
    revoke_permissions_for_current_directory()
