"""Sweep permission rules that point at deleted worktrees, then deduplicate.

The grant flow mints per-worktree allow/deny rules into ~/.claude/settings.json
and the revoke flow removes them, but a revoke that never runs leaves rules
for deleted worktrees behind, and they pile up run after run. Before the grant
and revoke flows write, they call this sweep so the settings hold no rule for a
worktree directory that is gone::

    allow:  Edit(<root>/repo/live/.claude/**)   live on disk  -> kept
            Edit(<root>/repo/gone/.claude/**)   deleted       -> dropped
            Edit(<root>/repo/live/.claude/**)   duplicate     -> dropped

A rule whose target lies outside the worktrees root is left untouched.
"""

from pathlib import Path

from _claude_permissions_common import remove_matching_entries_from_list
from pr_loop_shared_constants.claude_settings_keys_constants import (
    CLAUDE_SETTINGS_ALLOW_KEY,
    CLAUDE_SETTINGS_DENY_KEY,
    CLAUDE_SETTINGS_PERMISSIONS_KEY,
)
from pr_loop_shared_constants.stale_worktree_rule_sweep_constants import (
    get_claude_worktrees_root,
    worktree_directory_for_rule,
)


def _is_stale_worktree_rule(candidate_rule: object, worktrees_root: Path) -> bool:
    if not isinstance(candidate_rule, str):
        return False
    worktree_directory = worktree_directory_for_rule(candidate_rule, worktrees_root)
    if worktree_directory is None:
        return False
    return not worktree_directory.exists()


def _deduplicate_list_preserving_order(all_entries: list[object]) -> int:
    all_unique_entries: list[object] = []
    for each_entry in all_entries:
        if each_entry not in all_unique_entries:
            all_unique_entries.append(each_entry)
    removed_count = len(all_entries) - len(all_unique_entries)
    all_entries[:] = all_unique_entries
    return removed_count


def _sweep_and_deduplicate_rule_list(
    all_rules: list[object], worktrees_root: Path
) -> int:
    stale_removed_count = remove_matching_entries_from_list(
        all_rules,
        lambda candidate_rule: _is_stale_worktree_rule(candidate_rule, worktrees_root),
    )
    duplicate_removed_count = _deduplicate_list_preserving_order(all_rules)
    return stale_removed_count + duplicate_removed_count


def _permission_rule_list(
    all_settings: dict[str, object], list_key: str
) -> list[object] | None:
    permissions_section = all_settings.get(CLAUDE_SETTINGS_PERMISSIONS_KEY)
    if not isinstance(permissions_section, dict):
        return None
    rule_list = permissions_section.get(list_key)
    if not isinstance(rule_list, list):
        return None
    return rule_list


def sweep_and_deduplicate_permission_lists(
    all_settings: dict[str, object], worktrees_root: Path
) -> int:
    """Drop stale worktree rules and duplicates from the allow and deny lists.

    Args:
        all_settings: The parsed ~/.claude/settings.json dictionary, mutated
            in place.
        worktrees_root: The ~/.claude/worktrees directory rules live under.

    Returns:
        The total count of rules removed across both lists.
    """
    total_removed_count = 0
    for each_list_key in (CLAUDE_SETTINGS_ALLOW_KEY, CLAUDE_SETTINGS_DENY_KEY):
        rule_list = _permission_rule_list(all_settings, each_list_key)
        if rule_list is None:
            continue
        total_removed_count += _sweep_and_deduplicate_rule_list(
            rule_list, worktrees_root
        )
    return total_removed_count


def sweep_stale_worktree_rules_from_settings(all_settings: dict[str, object]) -> int:
    """Sweep the settings against the real ~/.claude/worktrees root on disk.

    Args:
        all_settings: The parsed ~/.claude/settings.json dictionary, mutated
            in place.

    Returns:
        The total count of rules removed across the allow and deny lists.
    """
    worktrees_root = get_claude_worktrees_root()
    return sweep_and_deduplicate_permission_lists(all_settings, worktrees_root)
