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
    ("A", "API contract verification"),
    ("B", "Selector / query / engine compatibility"),
    ("C", "Resource cleanup and lifecycle"),
    ("D", "Variable scoping, ordering, and unbound references"),
    ("E", "Dead code and unused imports"),
    ("F", "Silent failures"),
    ("G", "Off-by-one, bounds, integer overflow"),
    ("H", "Security boundaries"),
    ("I", "Concurrency hazards"),
    ("J", "CODE_RULES.md compliance"),
    ("K", "Codebase conflicts (incomplete propagation)"),
    ("L", "Behavior-equivalence for refactors"),
    ("M", "Producer/consumer cardinality vs collection-type contract"),
    ("N", "Test-name scenario verifier"),
]

AUDIT_RUBRIC_REFERENCE_TEXT = (
    "The category list above is a summary. The binding definition of each "
    "category is its rubric file under $HOME/.claude/audit-rubrics/category_rubrics/ "
    "(ready-to-send prompt variants under $HOME/.claude/audit-rubrics/prompts/). "
    "Read the rubric files before auditing."
)

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

ALL_FINDING_BODY_ELEMENT_KEYS: tuple[str, ...] = (
    "title",
    "excerpt",
    "description",
)

ALL_FIX_OUTCOME_BODY_ELEMENT_KEYS: tuple[str, ...] = (
    "reason",
    "hook_output",
)
