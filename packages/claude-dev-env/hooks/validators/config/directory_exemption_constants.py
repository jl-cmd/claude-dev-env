"""Directory-exemption segment names for validator path checks."""

ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES: frozenset[str] = frozenset(
    {"scripts", "tests", "migrations", "workflow", "config", "hooks"}
)
ALL_CLAUDE_HOOKS_PARENT_AND_CHILD_SEGMENTS: tuple[str, str] = (".claude", "hooks")
