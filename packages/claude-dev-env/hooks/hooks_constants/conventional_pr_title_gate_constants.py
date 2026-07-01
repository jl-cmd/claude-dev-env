"""Configuration constants for the conventional_pr_title_gate PreToolUse hook."""

import re

ALL_GH_EXECUTABLE_BASENAMES: frozenset[str] = frozenset({"gh", "gh.exe"})
PR_SUBCOMMAND_TOKEN: str = "pr"
ALL_PR_TITLE_SUBCOMMAND_VERBS: frozenset[str] = frozenset({"create", "edit"})
GH_PR_SUBCOMMAND_MINIMUM_TOKEN_COUNT: int = 3

BASH_TOOL_NAME: str = "Bash"

TITLE_LONG_FLAG: str = "--title"
TITLE_SHORT_FLAG: str = "-t"
REPO_LONG_FLAG: str = "--repo"
REPO_SHORT_FLAG: str = "-R"

WORKFLOWS_DIRECTORY_RELATIVE_PATH: str = ".github/workflows"
ALL_WORKFLOW_FILE_GLOB_PATTERNS: tuple[str, ...] = ("*.yml", "*.yaml")

ALL_SEMANTIC_TITLE_CI_MARKERS: tuple[str, ...] = (
    "semantic-pull-request",
    "action-semantic-pull-request",
    "semantic_pull_request",
)

ALL_CONVENTIONAL_COMMIT_TYPES: tuple[str, ...] = (
    "feat",
    "fix",
    "chore",
    "docs",
    "refactor",
    "perf",
    "ci",
    "style",
    "test",
    "build",
    "revert",
)

CONVENTIONAL_COMMIT_TITLE_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:" + "|".join(ALL_CONVENTIONAL_COMMIT_TYPES) + r")(?:\([^)]+\))?!?: .+"
)

SEMANTIC_ACTION_TYPES_INPUT_PATTERN: re.Pattern[str] = re.compile(r"^\s*types\s*:")

SEMANTIC_ACTION_FLOW_TYPES_INPUT_PATTERN: re.Pattern[str] = re.compile(r"[{,]\s*types\s*:")

YAML_LIST_ITEM_PREFIX: str = "- "

CORRECTIVE_MESSAGE: str = (
    "BLOCKED [conventional-pr-title]: this repository's CI validates PR titles "
    "against Conventional Commits, and the --title value here does not match. "
    "Required shape: type(scope)!: description, where the scope and the "
    "breaking-change marker (!) are optional. Allowed types: "
    f"{', '.join(ALL_CONVENTIONAL_COMMIT_TYPES)}.\n\n"
    "Example: feat(hooks): add the conventional PR title gate\n\n"
    "Fix the --title value and retry."
)
