"""Configuration constants for the PR-body numeric-claim accuracy check."""

from __future__ import annotations

import re

TEST_COUNT_CLAIM_PATTERN: re.Pattern[str] = re.compile(
    r"(?P<count>\d+)\s+(?:unit\s+)?tests?\b",
    re.IGNORECASE,
)
LINE_COUNT_CLAIM_PATTERN: re.Pattern[str] = re.compile(
    r"(?P<count>\d+)[-\s]lines?\b",
    re.IGNORECASE,
)
DIRECTORY_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_./-]*)/")
FILE_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_./-]*\.py)")
TEST_FUNCTION_DEFINITION_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*def (test_[A-Za-z0-9_]+)",
    re.MULTILINE,
)

TEST_FILE_GLOB: str = "test_*.py"
GIT_METADATA_DIRECTORY_NAME: str = ".git"
GIT_EXECUTABLE: str = "git"
GIT_SHOW_SUBCOMMAND: str = "show"
BASE_GIT_REF: str = "origin/main"
GIT_REF_PATH_SPEC_TEMPLATE: str = "{reference}:{relative_path}"
GIT_SHOW_TIMEOUT_SECONDS: int = 10

HOOK_SCRIPT_NAME: str = "pr_description_numeric_claims.py"
ALL_GH_PR_BODY_SUBCOMMAND_MARKERS: tuple[str, ...] = (
    "gh pr create",
    "gh pr edit",
    "gh pr comment",
)
DENY_REASON_PREFIX: str = "BLOCKED: [PR_NUMERIC_CLAIMS] "
DENY_REASON_JOIN: str = "; "
DENY_REASON_SUFFIX: str = (
    " -- re-measure each count against the repository and correct the PR body."
)

TEST_COUNT_MISMATCH_MESSAGE_TEMPLATE: str = (
    "PR body claims {claimed} test(s) for {path} but that directory defines "
    "{actual} -- correct the count to match the repository"
)
LINE_COUNT_MISMATCH_MESSAGE_TEMPLATE: str = (
    "PR body claims a {claimed}-line {path} but the file measures {actual} lines "
    "in the working tree and the base -- correct the count to match the repository"
)

__all__ = [
    "ALL_GH_PR_BODY_SUBCOMMAND_MARKERS",
    "BASE_GIT_REF",
    "DENY_REASON_JOIN",
    "DENY_REASON_PREFIX",
    "DENY_REASON_SUFFIX",
    "HOOK_SCRIPT_NAME",
    "DIRECTORY_TOKEN_PATTERN",
    "FILE_TOKEN_PATTERN",
    "GIT_EXECUTABLE",
    "GIT_METADATA_DIRECTORY_NAME",
    "GIT_REF_PATH_SPEC_TEMPLATE",
    "GIT_SHOW_SUBCOMMAND",
    "GIT_SHOW_TIMEOUT_SECONDS",
    "LINE_COUNT_CLAIM_PATTERN",
    "LINE_COUNT_MISMATCH_MESSAGE_TEMPLATE",
    "TEST_COUNT_CLAIM_PATTERN",
    "TEST_COUNT_MISMATCH_MESSAGE_TEMPLATE",
    "TEST_FILE_GLOB",
    "TEST_FUNCTION_DEFINITION_PATTERN",
]
