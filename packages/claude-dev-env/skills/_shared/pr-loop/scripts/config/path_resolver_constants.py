"""Path template constants for the bugteam / pr-loop shared scripts."""

import re

RUN_NAME_TEMPLATE_SINGLE = "bugteam-pr-{number}"
RUN_NAME_TEMPLATE_MULTI = "bugteam-{sanitized_branch}"
PER_PR_WORKSPACE_TEMPLATE = "pr-{number}"
WORKTREE_DIRNAME = "worktree"
DIFF_PATCH_TEMPLATE = "loop-{loop}.patch"
OUTCOME_XML_TEMPLATE = ".bugteam-pr{number}-loop{loop}.outcomes.xml"
FIX_OUTCOME_XML_TEMPLATE = ".bugteam-pr{number}-loop{loop}.fix-outcomes.xml"
LOOP_STATE_FILENAME = "loop-state.json"
SLUGIFY_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
SLUGIFY_REPLACEMENT = "-"
MULTI_PR_SLUG_TEMPLATE = "{owner}-{repo}-pr-{number}"
LOOP_STATE_JSON_INDENT = 2
ALL_VALID_FIX_STATUSES = frozenset({
    "fixed",
    "could_not_address",
    "hook_blocked",
    "unverified_fixed",
})

ALL_AUDIT_CONSTRAINT_TEXTS = [
    "Work exclusively within the worktree directory.",
    "Every finding must cite file:line.",
    "Document each finding with severity, file, line, and suggested fix.",
    "Read each file in the diff before reporting on it.",
]

ALL_AUDIT_CATEGORY_ENTRIES = [
    ("A", "Documentation / API call accuracy"),
    ("B", "Type safety / boundary types"),
    ("C", "Magic values / hardcoded constants"),
    ("D", "Naming / banned identifiers"),
    ("E", "Orphans / dead code"),
    ("F", "Error handling / bare except"),
    ("G", "Bounds / silent cap exits"),
    ("H", "Testing / test quality"),
    ("I", "Control flow / logic errors"),
    ("J", "Architecture / SOLID violations"),
    ("K", "Codebase conflicts / DRY"),
]

ALL_FIX_EXECUTION_STEPS = [
    "Read the finding and verify it against the current file at file:line.",
    "Write a failing test that reproduces the bug.",
    "Implement the smallest change that resolves the finding.",
    "Run the full test suite — confirm the new test and all existing tests pass.",
    "Stage and commit the fix with a descriptive message.",
    "Push the commit to the head branch.",
    "Post an inline reply on the finding thread confirming the fix.",
]

ALL_FIX_CONSTRAINT_TEXTS = [
    "Work exclusively within the worktree directory.",
    "Change only the lines directly related to each finding.",
    "Create one commit per fix loop, each focused on a single category of findings.",
    "Every fix must have a corresponding test.",
    "Remove deprecated code directly and update all call sites.",
    "Handle each error case with a named exception type.",
]

XML_PRETTY_INDENT = "  "
XML_SERIALIZE_ENCODING = "unicode"
XML_OUTPUT_ENCODING = "utf-8"
ALL_PYTHON_ONEXC_VERSION = (3, 12)
