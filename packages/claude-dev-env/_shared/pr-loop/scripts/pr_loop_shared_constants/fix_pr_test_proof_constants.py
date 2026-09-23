"""Constants for the fix pull request test-proof check."""

from __future__ import annotations

import re

FIX_TITLE_PATTERN: re.Pattern[str] = re.compile(r"^fix(\([^)]*\))?!?:")
ALL_PRODUCTION_CODE_SUFFIXES: tuple[str, ...] = (
    ".py",
    ".mjs",
    ".js",
    ".cjs",
    ".ts",
    ".tsx",
    ".ps1",
    ".sh",
)
ALL_NODE_TEST_SUFFIXES: tuple[str, ...] = (".test.mjs", ".test.js", ".test.cjs")
ALL_NODE_TEST_COMMAND: tuple[str, ...] = ("node", "--test")
NODE_BASE_WORKTREE_TEMP_DIRECTORY_PREFIX: str = "fix_pr_test_proof_node_base_"
NODE_BASE_WORKTREE_DIRECTORY_NAME: str = "tree"
CI_CONFIG_DIRECTORY_NAME: str = ".github"
PASSED_EXIT_CODE: int = 0
FAILED_EXIT_CODE: int = 1

NOT_A_FIX_MESSAGE: str = "fix_pr_test_proof: the title is outside the fix type; nothing to prove."
NO_PRODUCTION_CHANGE_MESSAGE: str = (
    "fix_pr_test_proof: the fix changes no production code; nothing to prove."
)
NO_CHANGED_TEST_MESSAGE: str = (
    "fix_pr_test_proof: this fix changes production code and no Python or Node test. "
    "Add a test that fails on the base and passes on the head."
)
WORKTREE_FAILED_MESSAGE: str = (
    "fix_pr_test_proof: git could not check out the base revision {revision}."
)
HEAD_FAILURE_MESSAGE: str = (
    "fix_pr_test_proof: a changed test fails on the head in {group_root}. "
    "The proof test must pass once the fix is in."
)
NO_BASE_FAILURE_MESSAGE: str = (
    "fix_pr_test_proof: every changed test passes on the base {revision}. "
    "Add a test that fails without the fix."
)
PROVEN_MESSAGE: str = (
    "fix_pr_test_proof: {count} changed test(s) fail on the base and pass on the head."
)
