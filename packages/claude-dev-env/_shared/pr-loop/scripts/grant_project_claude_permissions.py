"""Grant Edit/Read permissions on the current directory's .claude tree.

Run from the project root whose .claude/** you want a Claude Code session
(including spawned subagents) to edit without prompting. Writes idempotent
entries into the user-scope settings at ~/.claude/settings.json and prints
the changes applied. No-op when the entries already exist.
"""

import sys
from pathlib import Path

parent_directory = str(Path(__file__).resolve().parent)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)

from _claude_permissions_common import (  # noqa: E402
    append_if_missing,
    build_agent_config_deny_rules,
    build_permission_rules,
    ensure_dict_section,
    ensure_list_entry,
    exit_with_error,
    get_current_project_path,
    is_trust_entry_for_project,
    is_valid_project_root,
    load_settings,
    remove_matching_entries_from_list,
    save_settings,
)
from pr_loop_shared_constants.claude_permissions_constants import (
    ALL_AGENT_CONFIG_DENY_TOOLS,
    ALL_AGENT_CONFIG_PATH_PATTERNS,
    ALL_PERMISSION_ALLOW_TOOLS,
    AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX,
    AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE,
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


def add_rules_to_allow_list(
    all_settings: dict[str, object], all_rules_to_add: list[str]
) -> int:
    """Add permission rules to the settings allow list.

    Args:
        all_settings: The parsed settings dictionary.
        all_rules_to_add: Permission rule strings to append.

    Returns:
        Number of rules actually added (new entries).
    """
    permissions_section = ensure_dict_section(
        all_settings, CLAUDE_SETTINGS_PERMISSIONS_KEY
    )
    existing_allow_list = ensure_list_entry(
        permissions_section, CLAUDE_SETTINGS_ALLOW_KEY
    )
    return sum(
        1
        for each_rule in all_rules_to_add
        if append_if_missing(existing_allow_list, each_rule)
    )


def add_rules_to_deny_list(
    all_settings: dict[str, object], all_rules_to_add: list[str]
) -> int:
    """Add permission rules to the settings deny list.

    Deny rules take precedence over allow rules in Claude Code's permission
    matching, so writing agent-config paths into the deny list forces a
    per-edit user approval even when a broader allow rule would cover them.

    Args:
        all_settings: The parsed settings dictionary.
        all_rules_to_add: Permission rule strings to append.

    Returns:
        Number of rules actually added (new entries).
    """
    permissions_section = ensure_dict_section(
        all_settings, CLAUDE_SETTINGS_PERMISSIONS_KEY
    )
    existing_deny_list = ensure_list_entry(
        permissions_section, CLAUDE_SETTINGS_DENY_KEY
    )
    return sum(
        1
        for each_rule in all_rules_to_add
        if append_if_missing(existing_deny_list, each_rule)
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
    permissions_section = ensure_dict_section(
        all_settings, CLAUDE_SETTINGS_PERMISSIONS_KEY
    )
    existing_directories = ensure_list_entry(
        permissions_section, CLAUDE_SETTINGS_ADDITIONAL_DIRECTORIES_KEY
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
    auto_mode_section = ensure_dict_section(
        all_settings, CLAUDE_SETTINGS_AUTO_MODE_KEY
    )
    existing_environment = ensure_list_entry(
        auto_mode_section, CLAUDE_SETTINGS_ENVIRONMENT_KEY
    )
    if append_if_missing(existing_environment, entry_text):
        return 1
    return 0


def _is_stale_trust_entry(
    candidate_entry: object,
    project_path: str,
    prefix: str,
    protected_entry: str | None,
) -> bool:
    if not is_trust_entry_for_project(candidate_entry, project_path, prefix):
        return False
    if protected_entry is not None and candidate_entry == protected_entry:
        return False
    return True


def purge_stale_trust_entries(
    all_settings: dict[str, object],
    project_path: str,
    prefix: str,
    protected_entry: str | None = None,
) -> int:
    """Remove every prior trust entry for the project from autoMode.environment.

    Args:
        all_settings: The parsed settings dictionary.
        project_path: The POSIX-style project root path.
        prefix: The literal prefix that marks a trust entry.
        protected_entry: When byte-equal to a candidate, prevents its removal.

    Returns:
        Number of stale entries removed.
    """
    auto_mode_section = all_settings.get(CLAUDE_SETTINGS_AUTO_MODE_KEY)
    if not isinstance(auto_mode_section, dict):
        return 0
    existing_environment = auto_mode_section.get(CLAUDE_SETTINGS_ENVIRONMENT_KEY)
    if not isinstance(existing_environment, list):
        return 0
    return remove_matching_entries_from_list(
        existing_environment,
        lambda candidate_entry: _is_stale_trust_entry(
            candidate_entry, project_path, prefix, protected_entry
        ),
    )


def _resolve_project_path_or_exit() -> str:
    project_root_path = Path.cwd()
    if not is_valid_project_root(project_root_path):
        print(
            f"ERROR: cwd {project_root_path} is not a project root "
            f"(no .git or .claude). Run from a project root.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return get_current_project_path()


def _build_grant_rule_sets(
    project_path: str,
) -> tuple[list[str], list[str], str]:
    all_permission_rules = build_permission_rules(
        project_path, ALL_PERMISSION_ALLOW_TOOLS
    )
    all_agent_config_deny_rules = build_agent_config_deny_rules(
        project_path,
        ALL_AGENT_CONFIG_DENY_TOOLS,
        ALL_AGENT_CONFIG_PATH_PATTERNS,
    )
    environment_entry = AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE.format(
        project_path=project_path
    )
    return (all_permission_rules, all_agent_config_deny_rules, environment_entry)


def _apply_grant(
    all_settings: dict[str, object],
    project_path: str,
    all_grant_rule_sets: tuple[list[str], list[str], str],
) -> tuple[int, int, int, int, int]:
    all_permission_rules, all_agent_config_deny_rules, environment_entry = (
        all_grant_rule_sets
    )
    allow_added = add_rules_to_allow_list(all_settings, all_permission_rules)
    deny_added = add_rules_to_deny_list(all_settings, all_agent_config_deny_rules)
    dirs_added = add_directory_to_additional_directories(all_settings, project_path)
    purged = purge_stale_trust_entries(
        all_settings,
        project_path,
        AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX,
        protected_entry=environment_entry,
    )
    env_added = add_auto_mode_environment_entry(all_settings, environment_entry)
    return (allow_added, deny_added, dirs_added, purged, env_added)


def _print_no_change_notice(
    project_path: str, claude_user_settings_path: Path
) -> None:
    print(f"Project path: {project_path}")
    print(f"Settings file: {claude_user_settings_path}")
    print("No changes needed; settings file left untouched.")


def _print_grant_summary(
    project_path: str,
    claude_user_settings_path: Path,
    all_grant_rule_sets: tuple[list[str], list[str], str],
    all_change_counts: tuple[int, int, int, int, int],
) -> None:
    all_permission_rules, all_agent_config_deny_rules, _ = all_grant_rule_sets
    allow_added, deny_added, dirs_added, purged, env_added = all_change_counts
    print(f"Project path: {project_path}")
    print(f"Settings file: {claude_user_settings_path}")
    print(f"Allow rules added: {allow_added} of {len(all_permission_rules)}")
    print(f"Deny rules added: {deny_added} of {len(all_agent_config_deny_rules)}")
    print(f"Additional directories added: {dirs_added}")
    if purged > 0:
        print(f"Stale auto-mode environment entries purged: {purged}")
    print(f"Auto-mode environment entries added: {env_added}")


def grant_permissions_for_current_directory() -> None:
    """Grant Edit/Read permissions for the current project directory.

    Builds allow and agent-config deny rules from config, writes them to the
    user settings, and prints the counts applied. A fresh grant reports::

        Allow rules added: 2 of 2
        Deny rules added: 14 of 14
        Additional directories added: 1
        Auto-mode environment entries added: 1

    Raises:
        SystemExit: When the current directory is not a valid project root.
        ValueError: Propagated from get_current_project_path() when the path
                    contains glob metacharacters.
    """
    claude_user_settings_path: Path = get_claude_user_settings_path()
    project_path = _resolve_project_path_or_exit()
    grant_rule_sets = _build_grant_rule_sets(project_path)
    settings = load_settings(claude_user_settings_path)
    worktree_sweep_removed_count = sweep_stale_worktree_rules_from_settings(settings)
    change_counts = _apply_grant(settings, project_path, grant_rule_sets)
    if sum(change_counts) + worktree_sweep_removed_count == 0:
        _print_no_change_notice(project_path, claude_user_settings_path)
        return
    save_settings(claude_user_settings_path, settings)
    _print_grant_summary(
        project_path, claude_user_settings_path, grant_rule_sets, change_counts
    )


if __name__ == "__main__":
    try:
        grant_permissions_for_current_directory()
    except ValueError as path_error:
        exit_with_error(str(path_error))
