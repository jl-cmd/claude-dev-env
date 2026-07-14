"""Path template constants for the bugteam / pr-loop shared scripts."""

import re

RUN_NAME_TEMPLATE_SINGLE = "bugteam-pr-{number}"
RUN_NAME_TEMPLATE_MULTI = "bugteam-{sanitized_branch}"
PER_PR_WORKSPACE_TEMPLATE = "pr-{number}"
WORKTREE_DIRNAME = "worktree"
DIFF_PATCH_TEMPLATE = "loop-{loop}.patch"
OUTCOME_XML_TEMPLATE = ".bugteam-pr{number}-loop{loop}.outcomes.xml"
FIX_OUTCOME_XML_TEMPLATE = ".bugteam-pr{number}-loop{loop}.fix-outcomes.xml"
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
    "Double-quote every path in shell commands and write paths with "
    "forward slashes (e.g. C:/Users/...), even on Windows.",
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
    ("O", "Docstring / fixture-prose vs implementation drift"),
    ("P", "Name / regex / word-list vs behavior-contract precision"),
    ("Q", "Cross-surface claim consistency (terminology, PR-description claims, message-vs-guard)"),
]

AUDIT_RUBRIC_REFERENCE_TEXT = (
    "The category list above is a summary. The binding definition of each "
    "category is its rubric file under $HOME/.claude/audit-rubrics/category_rubrics/ "
    "(ready-to-send prompt variants under $HOME/.claude/audit-rubrics/prompts/). "
    "Read the rubric files before auditing."
)

AUDIT_PROMPT_FLAVOR_AGENT = "agent"
AUDIT_PROMPT_FLAVOR_HEADLESS = "headless"
ALL_AUDIT_PROMPT_FLAVORS = frozenset({
    AUDIT_PROMPT_FLAVOR_AGENT,
    AUDIT_PROMPT_FLAVOR_HEADLESS,
})

AUDIT_COMMENT_POSTING_AGENT_TEXT = (
    "Post findings as inline review comments on the PR via "
    "the GitHub MCP add_comment_to_pending_review tool. "
    "Group related findings into a single pending review."
)
AUDIT_COMMENT_POSTING_HEADLESS_TEXT = (
    "Do not post reviews or comments. Use gh only when you must read "
    "PR metadata. Write findings into the outcome XML named in "
    "<output_format>. The lead session posts the review with "
    "post_audit_thread.py after the worker exits."
)
AUDIT_OUTPUT_FORMAT_AGENT_TEXT = (
    "Emit findings as JSON array of objects with keys: "
    "severity (P0/P1/P2), file, line, category, message, suggestion."
)
AUDIT_OUTPUT_FORMAT_HEADLESS_TEMPLATE = (
    "Write the complete audit outcome XML to {outcome_path}. "
    "Leave review_url empty when the lead posts after you exit. "
    "Do not use TaskCreate, MCP tools, or Artifact tools."
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

ALL_FIX_EXECUTION_STEPS_HEADLESS = [
    "Read the finding and verify it against the current file at file:line.",
    "Write a failing test that reproduces the bug.",
    "Implement the smallest change that resolves the finding.",
    "Run the full test suite — confirm the new test and all existing tests pass.",
    "Leave the working tree dirty with your edits. Do not stage, commit, or push.",
]

ALL_FIX_CONSTRAINT_TEXTS = [
    "Work exclusively within the worktree directory.",
    "Change only the lines directly related to each finding.",
    "Create one commit per fix loop, each focused on a single category of findings.",
    "Every fix must have a corresponding test.",
    "Remove deprecated code directly and update all call sites.",
    "Handle each error case with a named exception type.",
    "Double-quote every path in shell commands and write paths with "
    "forward slashes (e.g. C:/Users/...), even on Windows.",
]

ALL_FIX_CONSTRAINT_TEXTS_HEADLESS = [
    "Work exclusively within the worktree directory.",
    "Change only the lines directly related to each finding.",
    "Every fix must have a corresponding test.",
    "Remove deprecated code directly and update all call sites.",
    "Handle each error case with a named exception type.",
    "Do not stage, commit, or push. The lead owns git write operations.",
    "Do not use TaskCreate, MCP tools, or Artifact tools.",
    "Double-quote every path in shell commands and write paths with "
    "forward slashes (e.g. C:/Users/...), even on Windows.",
]

FIX_PROMPT_FLAVOR_AGENT = "agent"
FIX_PROMPT_FLAVOR_HEADLESS = "headless"
ALL_FIX_PROMPT_FLAVORS = frozenset({
    FIX_PROMPT_FLAVOR_AGENT,
    FIX_PROMPT_FLAVOR_HEADLESS,
})

FIX_COMMENT_POSTING_AGENT_TEXT = (
    "After commit, post one reply per finding thread via the GitHub MCP "
    "add_reply_to_pull_request_comment tool, then resolve the thread."
)
FIX_COMMENT_POSTING_HEADLESS_TEXT = (
    "Do not post replies or resolve threads. Use gh only when you must read "
    "PR metadata. Write per-finding outcomes into the outcome XML named in "
    "<output_format>. The lead session posts replies after the worker exits."
)
FIX_OUTPUT_FORMAT_AGENT_TEXT = (
    "After posting replies, write the complete fix outcome XML "
    "(schema in PROMPTS.md)."
)
FIX_OUTPUT_FORMAT_HEADLESS_TEMPLATE = (
    "Write the complete fix outcome XML to {outcome_path}. "
    "Leave commit_sha empty when the lead commits after you exit. "
    "Do not use TaskCreate, MCP tools, or Artifact tools."
)

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
