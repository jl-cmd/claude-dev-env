"""Configuration constants for the proof-of-work PR-comment audit.

Holds the proof-part detection patterns, the gap and linkage word lists,
the gh command tokens the audit runs to read a PR's comments and diff, and
the corrective messages returned when a proof part is missing or when
``gh pr ready`` runs with no passing proof comment on the PR.
"""

from __future__ import annotations

import re

ALL_PROOF_HEADING_KEYWORDS: tuple[str, ...] = ("proof", "verification")

PR_READY_INVOCATION_PATTERN: re.Pattern[str] = re.compile(r"(?:^|[;&|])\s*gh\s+pr\s+ready\b")
PR_READY_UNDO_FLAG: str = "--undo"

GH_EXECUTABLE: str = "gh"
GH_API_SUBCOMMAND: str = "api"
GH_REPO_FLAG: str = "--repo"
REPO_SLUG_TEMPLATE: str = "{owner}/{repo}"
GH_PAGINATE_FLAG: str = "--paginate"
GH_SLURP_FLAG: str = "--slurp"
PR_COMMENTS_API_PATH_TEMPLATE: str = "repos/{{owner}}/{{repo}}/issues/{pr_number}/comments"
ALL_PR_DIFF_SUBCOMMANDS: tuple[str, ...] = ("pr", "diff")
PR_DIFF_NAME_ONLY_FLAG: str = "--name-only"
ALL_PR_VIEW_NUMBER_ARGUMENTS: tuple[str, ...] = ("pr", "view", "--json", "number")
PR_NUMBER_JSON_FIELD: str = "number"
COMMENT_BODY_JSON_FIELD: str = "body"
GH_COMMAND_TIMEOUT_SECONDS: int = 6
MAX_DIFF_SCAN_CHARS: int = 200000

ALL_VISUAL_FILE_SUFFIXES: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico", ".html", ".css"}
)
HEX_COLOR_ADDED_LINE_PATTERN: re.Pattern[str] = re.compile(r"^\+.*#[0-9A-Fa-f]{6}\b", re.MULTILINE)
IMAGE_EMBED_PATTERN: re.Pattern[str] = re.compile(r"!\[[^\]]*\]\([^)\s]+\)")
ISSUE_REFERENCE_PATTERN: re.Pattern[str] = re.compile(r"#\d+")
PLAN_LINKAGE_KEYWORD_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:issue|phase|plan|parent|advanc\w*|milestone|part of)\b", re.IGNORECASE
)
DIGIT_PATTERN: re.Pattern[str] = re.compile(r"\d")
ALL_HONEST_GAP_PHRASES: tuple[str, ...] = (
    "gap",
    "limitation",
    "cannot",
    "does not show",
    "not shown",
    "unverified",
    "not covered",
)

PROOF_PART_COMMAND_MESSAGE: str = (
    "proof comment missing a fenced command block showing the exact command(s) run on real data"
)
PROOF_PART_MEASURED_MESSAGE: str = (
    "proof comment missing a measured-value element -- add a table row or bullet fact carrying "
    "the numbers read from the produced artifact"
)
PROOF_PART_PLAN_LINKAGE_MESSAGE: str = (
    "proof comment missing a plan-linkage sentence -- add one line naming the parent issue or "
    "phase this PR advances, with its #number"
)
PROOF_PART_VISUAL_MESSAGE: str = (
    "proof comment missing a visual element on a visual change -- embed an image (color "
    "swatches, before/after screenshots) for values a human cannot read at a glance"
)
PROOF_PART_HONEST_GAPS_MESSAGE: str = (
    "proof comment missing an honest-gaps statement -- say plainly what this offline proof "
    "cannot show and what covers that gap"
)

PR_READY_GATE_MESSAGE_TEMPLATE: str = (
    "BLOCKED: [PROOF_OF_WORK] PR #{pr_number} carries no passing proof-of-work comment. "
    "Post one comment with a proof or verification heading carrying: "
    "(1) the exact command(s) run on real data in a fenced code block, "
    "(2) measured outcomes from the produced artifact as a table row or bullet facts, "
    "(3) one sentence naming the parent issue or phase this PR advances, with its #number, "
    "(4) an image embed when the diff touches images, HTML, CSS, or hex color values, and "
    "(5) an honest statement of what the offline proof cannot show. "
    "Then re-run gh pr ready."
)

__all__ = [
    "ALL_HONEST_GAP_PHRASES",
    "ALL_PROOF_HEADING_KEYWORDS",
    "ALL_PR_DIFF_SUBCOMMANDS",
    "ALL_PR_VIEW_NUMBER_ARGUMENTS",
    "ALL_VISUAL_FILE_SUFFIXES",
    "COMMENT_BODY_JSON_FIELD",
    "DIGIT_PATTERN",
    "GH_API_SUBCOMMAND",
    "GH_COMMAND_TIMEOUT_SECONDS",
    "GH_EXECUTABLE",
    "GH_PAGINATE_FLAG",
    "GH_REPO_FLAG",
    "GH_SLURP_FLAG",
    "HEX_COLOR_ADDED_LINE_PATTERN",
    "IMAGE_EMBED_PATTERN",
    "ISSUE_REFERENCE_PATTERN",
    "MAX_DIFF_SCAN_CHARS",
    "PLAN_LINKAGE_KEYWORD_PATTERN",
    "PROOF_PART_COMMAND_MESSAGE",
    "PROOF_PART_HONEST_GAPS_MESSAGE",
    "PROOF_PART_MEASURED_MESSAGE",
    "PROOF_PART_PLAN_LINKAGE_MESSAGE",
    "PROOF_PART_VISUAL_MESSAGE",
    "PR_COMMENTS_API_PATH_TEMPLATE",
    "PR_DIFF_NAME_ONLY_FLAG",
    "PR_NUMBER_JSON_FIELD",
    "PR_READY_GATE_MESSAGE_TEMPLATE",
    "PR_READY_INVOCATION_PATTERN",
    "PR_READY_UNDO_FLAG",
    "REPO_SLUG_TEMPLATE",
]
