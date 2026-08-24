"""Shared configuration for the sync-to-cursor package."""

GENERATOR_VERSION: str = "1.3.0"
ALL_CANONICAL_DOC_FILES: tuple[str, ...] = ("CODE_RULES.md", "TEST_QUALITY.md")
MAX_RULE_BODY_LINES: int = 50
ALL_SKIPPED_RULE_FILE_NAMES: frozenset[str] = frozenset({"CLAUDE.md", "AGENTS.md"})
MARKDOWN_SUFFIX: str = ".md"
CLAUDE_RULES_DIRECTORY_NAME: str = "rules"
