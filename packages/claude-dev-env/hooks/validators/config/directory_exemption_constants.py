"""Directory-segment names that anchor validator temp-path staging.

``validate_proposed_file`` keeps the target's path from the first segment named
here, so the staged copy matches the real path's exemptions. The names combine
the authoritative config directories with the script, test, migration, workflow,
and ``.claude/hooks`` directories.
"""

from hooks_constants.code_rules_path_utils_constants import ALL_CONFIG_DIRECTORY_NAMES

ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES: frozenset[str] = ALL_CONFIG_DIRECTORY_NAMES | frozenset(
    {"scripts", "tests", "migrations", "workflow", "hooks"}
)
ALL_CLAUDE_HOOKS_PARENT_AND_CHILD_SEGMENTS: tuple[str, str] = (".claude", "hooks")
