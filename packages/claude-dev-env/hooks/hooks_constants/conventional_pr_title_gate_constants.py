"""Configuration constants for the conventional_pr_title_gate PreToolUse hook."""

import re

GH_PR_TITLE_SUBCOMMAND_PATTERN: re.Pattern[str] = re.compile(
    r"\bgh\s+pr\s+(?:create|edit)\b",
    re.IGNORECASE,
)

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

CORRECTIVE_MESSAGE: str = (
    "BLOCKED [conventional-pr-title]: this repository's CI validates PR titles "
    "against Conventional Commits, and the --title value here does not match. "
    "Required shape: type(scope)!: description, where the scope and the "
    "breaking-change marker (!) are optional. Allowed types: "
    f"{', '.join(ALL_CONVENTIONAL_COMMIT_TYPES)}.\n\n"
    "Example: feat(hooks): add the conventional PR title gate\n\n"
    "Fix the --title value and retry."
)
