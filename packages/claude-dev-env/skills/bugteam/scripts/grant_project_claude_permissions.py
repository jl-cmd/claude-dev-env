"""Grant Edit/Write/Read permissions on the current directory's .claude tree.

Run from the project root whose .claude/** you want a Claude Code session
(including spawned subagents) to edit without prompting. Writes idempotent
entries into the user-scope settings at ~/.claude/settings.json and prints
the changes applied. No-op when the entries already exist.
"""

import sys
from pathlib import Path

for each_cached_module_name in [
    each_module_key
    for each_module_key in list(sys.modules)
    if each_module_key == "config" or each_module_key.startswith("config.")
]:
    sys.modules.pop(each_cached_module_name, None)
parent_directory = str(Path(__file__).resolve().parent)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)

from _claude_permissions_common import (  # noqa: E402
    append_if_missing,
    build_permission_rules,
    ensure_dict_section,
    ensure_list_entry,
    exit_with_error,
    get_current_project_path,
    load_settings,
    save_settings,
)
from config.claude_permissions_common_constants import (  # noqa: E402
    ALL_PERMISSION_ALLOW_TOOLS,
    AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE,
    CLAUDE_DIRECTORY_MARKER,
    CLAUDE_USER_SETTINGS_FILENAME,
    GIT_DIRECTORY_MARKER,
    SETTINGS_ADDITIONAL_DIRECTORIES_KEY,
    SETTINGS_ALLOW_KEY,
    SETTINGS_AUTO_MODE_KEY,
    SETTINGS_ENVIRONMENT_KEY,
    SETTINGS_PERMISSIONS_KEY,
)


def is_valid_project_root(candidate_path: Path) -> bool:
    """Check whether a candidate path has expected project-root markers.

    Args:
        candidate_path: Path to check for project-root markers.

    Returns:
        True when the path contains .git or .claude directory.
    """
    return (
        (candidate_path / GIT_DIRECTORY_MARKER).exists()
        or (candidate_path / CLAUDE_DIRECTORY_MARKER).exists()
    )


def add_rules_to_allow_list(all_settings: dict[str, object], all_rules_to_add: list[str]) -> int:
    """Add permission rules to the settings allow list.

    Args:
        all_settings: The parsed settings dictionary.
        all_rules_to_add: Permission rule strings to append.

    Returns:
        Number of rules actually added (new entries).
    """
    permissions_section = ensure_dict_section(all_settings, SETTINGS_PERMISSIONS_KEY)
    existing_allow_list = ensure_list_entry(permissions_section, SETTINGS_ALLOW_KEY)
    return sum(
        1
        for each_rule in all_rules_to_add
        if append_if_missing(existing_allow_list, each_rule)
    )


def add_directory_to_additional_directories(
    all_settings: dict[str, object], directory_path: str
) -> int:
    """Add a project path to the additionalDirectories allow list.

    Args:
        all_settings: The parsed settings dictionary.
        directory_path: The project directory path to add.

    Returns:
        1 when the entry was added, 0 when it already existed.
    """
    permissions_section = ensure_dict_section(all_settings, SETTINGS_PERMISSIONS_KEY)
    existing_directories = ensure_list_entry(
        permissions_section, SETTINGS_ADDITIONAL_DIRECTORIES_KEY
    )
    if append_if_missing(existing_directories, directory_path):
        return 1
    return 0


def add_auto_mode_environment_entry(
    all_settings: dict[str, object], entry_text: str
) -> int:
    """Add an auto-mode environment entry for the project.

    Args:
        all_settings: The parsed settings dictionary.
        entry_text: The environment entry text to add.

    Returns:
        1 when the entry was added, 0 when it already existed.
    """
    auto_mode_section = ensure_dict_section(all_settings, SETTINGS_AUTO_MODE_KEY)
    existing_environment = ensure_list_entry(auto_mode_section, SETTINGS_ENVIRONMENT_KEY)
    if append_if_missing(existing_environment, entry_text):
        return 1
    return 0


def grant_permissions_for_current_directory() -> None:
    """Grant Edit/Write/Read permissions for the current project directory.

    Reads the current project path, constructs permission rules from config
    constants, and writes them to ~/.claude/settings.json atomically.

    Raises:
        SystemExit(1): When the current directory is not a valid project root.
        ValueError: Propagated from get_current_project_path() when the path
                    contains glob metacharacters.
    """
    claude_user_settings_path: Path = (
        Path.home() / CLAUDE_DIRECTORY_MARKER / CLAUDE_USER_SETTINGS_FILENAME
    )
    project_root_path = Path.cwd()
    if not is_valid_project_root(project_root_path):
        print(
            f"ERROR: cwd {project_root_path} is not a project root "
            f"(no {GIT_DIRECTORY_MARKER} or {CLAUDE_DIRECTORY_MARKER}). Run from a project root.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    project_path = get_current_project_path()
    permission_rules = build_permission_rules(project_path, ALL_PERMISSION_ALLOW_TOOLS)
    environment_entry = AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE.format(
        project_path=project_path
    )
    settings = load_settings(claude_user_settings_path)
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
        print(f"Settings file: {claude_user_settings_path}")
        print("No changes needed; settings file left untouched.")
        return
    save_settings(claude_user_settings_path, settings)
    print(f"Project path: {project_path}")
    print(f"Settings file: {claude_user_settings_path}")
    print(f"Allow rules added: {rules_added_count} of {len(permission_rules)}")
    print(f"Additional directories added: {directories_added_count}")
    print(f"Auto-mode environment entries added: {environment_entries_added_count}")


if __name__ == "__main__":
    try:
        grant_permissions_for_current_directory()
    except ValueError as path_error:
        exit_with_error(str(path_error))
