"""Revoke the permissions previously granted by grant_project_claude_permissions.

Run from the same project root you previously granted. Removes the matching
allow rules, the additionalDirectories entry, and the autoMode environment
entry from ~/.claude/settings.json. Safe to run when no prior grant exists.
After removals, prunes any newly empty lists and their parent permissions or
autoMode sections so repeated grant/revoke cycles leave no dead structure.
"""

import sys
from pathlib import Path

parent_directory = str(Path(__file__).resolve().parent)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)

from _claude_permissions_common import (  # noqa: E402
    all_project_path_aliases_for_reap,
    build_agent_config_deny_rules,
    build_permission_rules,
    exit_with_error,
    get_current_project_path,
    is_inert_file_permission_rule,
    is_trust_entry_for_project,
    is_valid_project_root,
    load_settings,
    prune_empty_list_then_empty_section,
    remove_matching_entries_from_list,
    save_settings,
)
from pr_loop_shared_constants.claude_permissions_constants import (
    ALL_AGENT_CONFIG_DENY_TOOLS,
    ALL_AGENT_CONFIG_PATH_PATTERNS,
    ALL_LEGACY_PERMISSION_REAP_TOOLS,
    ALL_PERMISSION_ALLOW_TOOLS,
    AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX,
    INERT_RULES_REMOVED_LOG_PREFIX,
    get_claude_user_settings_path,
)
from pr_loop_shared_constants.claude_settings_keys_constants import (
    CLAUDE_SETTINGS_ADDITIONAL_DIRECTORIES_KEY,
    CLAUDE_SETTINGS_ALLOW_KEY,
    CLAUDE_SETTINGS_AUTO_MODE_KEY,
    CLAUDE_SETTINGS_DENY_KEY,
    CLAUDE_SETTINGS_ENVIRONMENT_KEY,
    CLAUDE_SETTINGS_PERMISSIONS_KEY,
)
from stale_worktree_rule_sweep import (  # noqa: E402
    sweep_stale_worktree_rules_from_settings,
)


def _reap_tool_names(all_mint_tool_names: tuple[str, ...]) -> tuple[str, ...]:
    """Return mint tool names plus legacy Write/Glob forms a revoke run reaps.

    Keeps mint tuples (Edit/Read) untouched and widens only the revoke surface
    so inert pre-#158 Write()/Glob() rules are removed with the current mint set.
    """
    return all_mint_tool_names + ALL_LEGACY_PERMISSION_REAP_TOOLS


def remove_inert_file_permission_rules(all_settings: dict[str, object]) -> int:
    """Remove Write/Glob/NotebookEdit allow and deny rules path-agnostically.

    ::

        remove_inert_file_permission_rules(
            {"permissions": {"allow": ["Write(/wt/**)", "Edit(/p/.claude/**)"]}}
        )  # ok: 1, allow left with Edit only

    Claude only honors Edit for file permission checks; leftover Write, Glob,
    and NotebookEdit rules from older grants only produce startup warnings.

    Args:
        all_settings: Parsed Claude user settings dictionary (mutated in place).

    Returns:
        Number of inert rules removed from allow and deny combined.
    """
    permissions_section = all_settings.get(CLAUDE_SETTINGS_PERMISSIONS_KEY)
    if not isinstance(permissions_section, dict):
        return 0
    total_removed_count = 0
    for each_list_key in (CLAUDE_SETTINGS_ALLOW_KEY, CLAUDE_SETTINGS_DENY_KEY):
        existing_rule_list = permissions_section.get(each_list_key)
        if not isinstance(existing_rule_list, list):
            continue
        total_removed_count += remove_matching_entries_from_list(
            existing_rule_list, is_inert_file_permission_rule
        )
    return total_removed_count


def build_project_scoped_allow_rules_for_reap(project_path: str) -> list[str]:
    """Build allow rules for every path alias of *project_path* (incl. $HOME).

    ::

        build_project_scoped_allow_rules_for_reap("/repo")
            # ok: includes Edit(/repo/.claude/**) and Write(/repo/.claude/**)

    Args:
        project_path: POSIX project root from get_current_project_path.

    Returns:
        Allow rule strings covering mint plus legacy tools for each path alias.
    """
    all_allow_rules: list[str] = []
    for each_path_alias in all_project_path_aliases_for_reap(project_path):
        all_allow_rules.extend(
            build_permission_rules(
                each_path_alias, _reap_tool_names(ALL_PERMISSION_ALLOW_TOOLS)
            )
        )
    return all_allow_rules


def build_project_scoped_deny_rules_for_reap(project_path: str) -> list[str]:
    """Build agent-config deny rules for every path alias of *project_path*.

    Args:
        project_path: POSIX project root from get_current_project_path.

    Returns:
        Deny rule strings for mint plus legacy tools across path aliases.
    """
    all_deny_rules: list[str] = []
    for each_path_alias in all_project_path_aliases_for_reap(project_path):
        all_deny_rules.extend(
            build_agent_config_deny_rules(
                each_path_alias,
                _reap_tool_names(ALL_AGENT_CONFIG_DENY_TOOLS),
                ALL_AGENT_CONFIG_PATH_PATTERNS,
            )
        )
    return all_deny_rules


def _remove_directory_and_trust_for_path_aliases(
    all_settings: dict[str, object], project_path: str
) -> tuple[int, int]:
    """Remove additionalDirectories and trust entries for each path alias."""
    directories_removed_count = 0
    environment_entries_removed_count = 0
    for each_path_alias in all_project_path_aliases_for_reap(project_path):
        directories_removed_count += remove_directory_from_additional_directories(
            all_settings, each_path_alias
        )
        environment_entries_removed_count += remove_trust_entries_for_project(
            all_settings, each_path_alias, AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX
        )
    return directories_removed_count, environment_entries_removed_count


def _print_revoke_summary(
    project_path: str,
    claude_user_settings_path: Path,
    allow_rules_removed_count: int,
    permission_rules_count: int,
    deny_rules_removed_count: int,
    agent_config_deny_rules_count: int,
    inert_rules_removed_count: int,
    directories_removed_count: int,
    environment_entries_removed_count: int,
) -> None:
    """Print the post-revoke summary lines to stdout."""
    inert_rules_removed_log_prefix = INERT_RULES_REMOVED_LOG_PREFIX
    print(f"Project path: {project_path}")
    print(f"Settings file: {claude_user_settings_path}")
    print(
        f"Allow rules removed: {allow_rules_removed_count} of {permission_rules_count}"
    )
    print(
        f"Deny rules removed: {deny_rules_removed_count} of "
        f"{agent_config_deny_rules_count}"
    )
    print(f"{inert_rules_removed_log_prefix}{inert_rules_removed_count}")
    print(f"Additional directories removed: {directories_removed_count}")
    print(
        f"Auto-mode environment entries removed: {environment_entries_removed_count}"
    )


def remove_values_from_list(
    all_target_list: list[object], all_values_to_remove: set[str]
) -> int:
    """Remove matching values from a list in place.

    Args:
        all_target_list: The list to remove values from.
        all_values_to_remove: Set of string values to remove.

    Returns:
        Number of values removed.
    """
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
    """Remove matching permission rules from the settings allow list.

    Args:
        all_settings: The parsed settings dictionary.
        all_rules_to_remove: Permission rule strings to remove.

    Returns:
        Number of rules removed.
    """
    permissions_section = all_settings.get(CLAUDE_SETTINGS_PERMISSIONS_KEY)
    if not isinstance(permissions_section, dict):
        return 0
    existing_allow_list = permissions_section.get(CLAUDE_SETTINGS_ALLOW_KEY)
    if not isinstance(existing_allow_list, list):
        return 0
    return remove_values_from_list(existing_allow_list, set(all_rules_to_remove))


def remove_rules_from_deny_list(
    all_settings: dict[str, object], all_rules_to_remove: list[str]
) -> int:
    """Remove matching permission rules from the settings deny list.

    Args:
        all_settings: The parsed settings dictionary.
        all_rules_to_remove: Permission rule strings to remove.

    Returns:
        Number of rules removed.
    """
    permissions_section = all_settings.get(CLAUDE_SETTINGS_PERMISSIONS_KEY)
    if not isinstance(permissions_section, dict):
        return 0
    existing_deny_list = permissions_section.get(CLAUDE_SETTINGS_DENY_KEY)
    if not isinstance(existing_deny_list, list):
        return 0
    return remove_values_from_list(existing_deny_list, set(all_rules_to_remove))


def remove_directory_from_additional_directories(
    all_settings: dict[str, object], directory_path: str
) -> int:
    """Remove a project path from the additionalDirectories list.

    Args:
        all_settings: The parsed settings dictionary.
        directory_path: The project directory path to remove.

    Returns:
        1 when the entry was removed, 0 when not found.
    """
    permissions_section = all_settings.get(CLAUDE_SETTINGS_PERMISSIONS_KEY)
    if not isinstance(permissions_section, dict):
        return 0
    existing_directories = permissions_section.get(
        CLAUDE_SETTINGS_ADDITIONAL_DIRECTORIES_KEY
    )
    if not isinstance(existing_directories, list):
        return 0
    return remove_values_from_list(existing_directories, {directory_path})


def remove_trust_entries_for_project(
    all_settings: dict[str, object], project_path: str, prefix: str
) -> int:
    """Remove every trust entry for the project from autoMode.environment.

    Matches any string in autoMode.environment whose prefix matches the
    trust-entry marker and that contains the project's .claude/** path.
    The match is wording-agnostic so prior template revisions are removed
    cleanly even when the current template differs.

    Args:
        all_settings: The parsed settings dictionary.
        project_path: The POSIX-style project root path.
        prefix: The literal prefix that marks a trust entry.

    Returns:
        Number of entries removed.
    """
    auto_mode_section = all_settings.get(CLAUDE_SETTINGS_AUTO_MODE_KEY)
    if not isinstance(auto_mode_section, dict):
        return 0
    existing_environment = auto_mode_section.get(CLAUDE_SETTINGS_ENVIRONMENT_KEY)
    if not isinstance(existing_environment, list):
        return 0
    return remove_matching_entries_from_list(
        existing_environment,
        lambda candidate_entry: is_trust_entry_for_project(
            candidate_entry, project_path, prefix
        ),
    )


def prune_settings_after_revoke(all_settings: dict[str, object]) -> None:
    """Remove empty lists and their parent sections after revoking entries.

    Args:
        all_settings: The parsed settings dictionary to prune in place.
    """
    prune_empty_list_then_empty_section(
        all_settings,
        CLAUDE_SETTINGS_PERMISSIONS_KEY,
        CLAUDE_SETTINGS_ALLOW_KEY,
    )
    prune_empty_list_then_empty_section(
        all_settings,
        CLAUDE_SETTINGS_PERMISSIONS_KEY,
        CLAUDE_SETTINGS_DENY_KEY,
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
    """Revoke permissions previously granted for the current project directory.

    Reads the current project path, constructs the matching allow and deny
    permission rules, removes them from ~/.claude/settings.json, removes
    every trust entry for the project from autoMode.environment, and prunes
    any newly empty sections.

    Raises:
        SystemExit: When the current directory is not a valid project root.
        ValueError: Propagated from get_current_project_path() when the path
                    contains glob metacharacters.
    """
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
    permission_rules = build_project_scoped_allow_rules_for_reap(project_path)
    all_agent_config_deny_rules = build_project_scoped_deny_rules_for_reap(
        project_path
    )
    settings = load_settings(claude_user_settings_path)
    worktree_sweep_removed_count = sweep_stale_worktree_rules_from_settings(settings)
    inert_rules_removed_count = remove_inert_file_permission_rules(settings)
    allow_rules_removed_count = remove_rules_from_allow_list(settings, permission_rules)
    deny_rules_removed_count = remove_rules_from_deny_list(
        settings, all_agent_config_deny_rules
    )
    directories_removed_count, environment_entries_removed_count = (
        _remove_directory_and_trust_for_path_aliases(settings, project_path)
    )
    total_changes_count = (
        allow_rules_removed_count
        + deny_rules_removed_count
        + directories_removed_count
        + environment_entries_removed_count
        + worktree_sweep_removed_count
        + inert_rules_removed_count
    )
    if total_changes_count == 0:
        print(f"Project path: {project_path}")
        print(f"Settings file: {claude_user_settings_path}")
        print("No changes to revoke; settings file left untouched.")
        return
    prune_settings_after_revoke(settings)
    save_settings(claude_user_settings_path, settings)
    _print_revoke_summary(
        project_path,
        claude_user_settings_path,
        allow_rules_removed_count,
        len(permission_rules),
        deny_rules_removed_count,
        len(all_agent_config_deny_rules),
        inert_rules_removed_count,
        directories_removed_count,
        environment_entries_removed_count,
    )


if __name__ == "__main__":
    try:
        revoke_permissions_for_current_directory()
    except ValueError as path_error:
        exit_with_error(str(path_error))
