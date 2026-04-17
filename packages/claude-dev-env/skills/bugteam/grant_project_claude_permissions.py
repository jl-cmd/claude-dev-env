"""Grant Edit/Write/Read permissions on the current directory's .claude tree.

Run from the project root whose .claude/** you want a Claude Code session
(including spawned subagents) to edit without prompting. Writes idempotent
entries into the user-scope settings at ~/.claude/settings.json and prints
the changes applied. No-op when the entries already exist.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _claude_permissions_common import (  # noqa: E402
    append_if_missing,
    build_permission_rules,
    ensure_dict_section,
    ensure_list_entry,
    exit_with_error,
    get_current_project_path,
    load_settings,
    save_settings,
    AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE,
    PERMISSION_ALLOW_TOOLS,
)


CLAUDE_USER_SETTINGS_PATH: Path = Path.home() / ".claude" / "settings.json"


def is_valid_project_root(candidate_path: Path) -> bool:
    git_marker_path = candidate_path / ".git"
    claude_marker_path = candidate_path / ".claude"
    return git_marker_path.exists() or claude_marker_path.exists()


def add_rules_to_allow_list(settings: dict[str, Any], rules_to_add: list[str]) -> int:
    permissions_section = ensure_dict_section(settings, "permissions")
    existing_allow_list = ensure_list_entry(permissions_section, "allow")
    return sum(
        1
        for each_rule in rules_to_add
        if append_if_missing(existing_allow_list, each_rule)
    )


def add_directory_to_additional_directories(
    settings: dict[str, Any], directory_path: str
) -> int:
    permissions_section = ensure_dict_section(settings, "permissions")
    existing_directories = ensure_list_entry(
        permissions_section, "additionalDirectories"
    )
    if append_if_missing(existing_directories, directory_path):
        return 1
    return 0


def add_auto_mode_environment_entry(settings: dict[str, Any], entry_text: str) -> int:
    auto_mode_section = ensure_dict_section(settings, "autoMode")
    existing_environment = ensure_list_entry(auto_mode_section, "environment")
    if append_if_missing(existing_environment, entry_text):
        return 1
    return 0


def grant_permissions_for_current_directory() -> None:
    project_root_path = Path.cwd()
    if not is_valid_project_root(project_root_path):
        print(
            f"ERROR: cwd {project_root_path} is not a project root "
            f"(no .git or .claude). Run from a project root.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    project_path = get_current_project_path()
    permission_rules = build_permission_rules(project_path, PERMISSION_ALLOW_TOOLS)
    environment_entry = AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE.format(
        project_path=project_path
    )
    settings = load_settings(CLAUDE_USER_SETTINGS_PATH)
    rules_added_count = add_rules_to_allow_list(settings, permission_rules)
    directories_added_count = add_directory_to_additional_directories(
        settings, project_path
    )
    environment_entries_added_count = add_auto_mode_environment_entry(
        settings, environment_entry
    )
    total_changes_count = (
        rules_added_count + directories_added_count + environment_entries_added_count
    )
    if total_changes_count == 0:
        print(f"Project path: {project_path}")
        print(f"Settings file: {CLAUDE_USER_SETTINGS_PATH}")
        print("No changes needed; settings file left untouched.")
        return
    save_settings(CLAUDE_USER_SETTINGS_PATH, settings)
    print(f"Project path: {project_path}")
    print(f"Settings file: {CLAUDE_USER_SETTINGS_PATH}")
    print(f"Allow rules added: {rules_added_count} of {len(permission_rules)}")
    print(f"Additional directories added: {directories_added_count}")
    print(f"Auto-mode environment entries added: {environment_entries_added_count}")


if __name__ == "__main__":
    try:
        grant_permissions_for_current_directory()
    except ValueError as path_error:
        exit_with_error(str(path_error))
