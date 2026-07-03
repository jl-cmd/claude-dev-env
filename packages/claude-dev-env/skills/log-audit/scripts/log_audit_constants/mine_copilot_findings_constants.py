"""Constants for the mine_copilot_findings script.

ALL_REVIEWER_BOT_LOGINS: the GitHub logins whose review comments count as defects.
PULLS_COMMENTS_ENDPOINT_TEMPLATE: the gh api path for a repo's pull-request comments.
RECENT_PULL_COUNT: how many recent pull requests a mining run reads.
MAX_EXAMPLES_PER_CLUSTER: example comment bodies kept per defect class.
KEYWORDS_BY_DEFECT_CLASS: lowercased substrings that sort a comment into a defect class.
PROPOSAL_BY_DEFECT_CLASS: the concrete skill-definition edit proposed for each class.
"""

ALL_REVIEWER_BOT_LOGINS = ("copilot-pull-request-reviewer[bot]", "cursor[bot]")
PULLS_COMMENTS_ENDPOINT_TEMPLATE = "repos/{repo}/pulls/comments"
RECENT_PULL_COUNT = 20
MAX_EXAMPLES_PER_CLUSTER = 3
KEYWORDS_BY_DEFECT_CLASS = {
    "missing-type-hint": ("type hint", "missing annotation", "untyped", "no return type"),
    "broad-except": ("broad except", "bare except", "except exception", "catch-all except"),
    "magic-value": ("magic number", "magic value", "hardcoded", "hard-coded"),
    "unclear-name": ("abbreviation", "unclear name", "rename this", "single-letter"),
    "missing-docstring": ("missing docstring", "no docstring", "undocumented"),
}
PROPOSAL_BY_DEFECT_CLASS = {
    "missing-type-hint": (
        "Tighten the code skill's type-hint rule to flag the untyped shape this "
        "class keeps hitting."
    ),
    "broad-except": (
        "Extend the no-broad-except enforcer pattern to the except shape this "
        "class keeps hitting."
    ),
    "magic-value": (
        "Extend the magic-value enforcer to the literal shape this class keeps "
        "hitting."
    ),
    "unclear-name": (
        "Add the abbreviation this class keeps flagging to the banned-identifier "
        "list."
    ),
    "missing-docstring": (
        "Tighten the public-docstring rule to the surface this class keeps "
        "hitting."
    ),
}