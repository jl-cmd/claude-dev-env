"""Constants and rule-format readers for stale_worktree_rule_sweep.

The worktrees root is derived from the same ~/.claude home the permission
grant script mints its rules under, so the location is named in exactly one
place. A worktree rule points at a directory two segments below that root::

    Edit(<claude home>/worktrees/<repository>/<worktree name>/.claude/**)
                                 ^^^^^^^^^^^^  ^^^^^^^^^^^^^^^
                                 segment 1     segment 2

    worktree_directory_for_rule(rule, root)  ->  <root>/<repository>/<worktree name>

A rule whose target path lies outside the worktrees root reads back as None,
so the sweep leaves it untouched.
"""

from pathlib import Path

from pr_loop_shared_constants.claude_permissions_constants import (
    get_claude_user_settings_path,
)

WORKTREES_SUBDIRECTORY_NAME: str = "worktrees"

WORKTREE_PATH_SEGMENT_COUNT: int = 2

RULE_PATH_OPEN_DELIMITER: str = "("

RULE_PATH_CLOSE_DELIMITER: str = ")"

CLAUDE_HOME_PATH_MARKER: str = "/.claude"


def get_claude_worktrees_root() -> Path:
    """Return the ~/.claude/worktrees directory the grant rules point under.

    Reuses get_claude_user_settings_path so the ~/.claude home is resolved
    in one place: the settings file's parent directory is the home, and the
    worktrees live directly beneath it.

    Returns:
        The absolute path to the user's worktrees root directory.
    """
    claude_home_directory = get_claude_user_settings_path().parent
    return claude_home_directory / WORKTREES_SUBDIRECTORY_NAME


def extract_rule_target_path(rule: str) -> str | None:
    """Return the path a permission rule targets, or None when unparsable.

    A rule reads ``Tool(<path>)``; the target is the text between the first
    open delimiter and the last close delimiter::

        Edit(/repo/wt/.claude/**)  ->  /repo/wt/.claude/**
        not a rule                 ->  None

    Args:
        rule: The permission rule string to read.

    Returns:
        The target path string, or None when the delimiters are absent.
    """
    open_index = rule.find(RULE_PATH_OPEN_DELIMITER)
    close_index = rule.rfind(RULE_PATH_CLOSE_DELIMITER)
    if open_index == -1 or close_index <= open_index:
        return None
    return rule[open_index + 1 : close_index]


def worktree_directory_for_rule(rule: str, worktrees_root: Path) -> Path | None:
    """Return the worktree directory a rule targets, or None when it is not one.

    Keeps the two segments below the worktrees root — repository, worktree::

        Edit(<root>/repo/wt/.claude/**)  ->  <root>/repo/wt
        Edit(/elsewhere/project/.claude/**)  ->  None

    Args:
        rule: The permission rule string to read.
        worktrees_root: The ~/.claude/worktrees directory rules live under.

    Returns:
        The worktree directory, or None when the target lies outside the
        worktrees root or is shallower than a worktree directory.
    """
    target_path = extract_rule_target_path(rule)
    if target_path is None:
        return None
    project_portion = target_path.rsplit(CLAUDE_HOME_PATH_MARKER, 1)[0]
    if not project_portion:
        return None
    try:
        relative_path = Path(project_portion).relative_to(worktrees_root)
    except ValueError:
        return None
    all_segments = relative_path.parts
    if len(all_segments) < WORKTREE_PATH_SEGMENT_COUNT:
        return None
    return worktrees_root.joinpath(*all_segments[:WORKTREE_PATH_SEGMENT_COUNT])
