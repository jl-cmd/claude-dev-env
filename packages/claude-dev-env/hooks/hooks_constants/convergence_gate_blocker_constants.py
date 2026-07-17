"""Command-parse patterns for the convergence gate's repo binding.

The convergence gate keys its evidence lookup to the PR that the
``gh pr ready`` command names. These patterns pull an explicit owner/repo
out of the command — and, for a full PR URL, the PR number too — so the
gate binds to the repository the command targets rather than the
session working directory's repository when the two differ.

The owner/repo and URL patterns run only over the ``gh pr ready`` segment,
clipped at the first command separator, so a flag or URL that belongs to a
chained command does not bind the gate to the wrong PR::

    gh pr ready 161 && gh pr comment 999 --repo other-owner/other-repo
    ^^^^^^^^^^^^^^^^                                    clipped here ^
    -> ready segment scanned; the chained --repo is out of scope

    gh pr ready 161 --repo sample-owner/target-repo
                    ^^^^^^ ^^^^^^^^^^^^ ^^^^^^^^^^^
                    flag   owner        repo         -> REPO_OVERRIDE_FLAG_PATTERN
    gh pr ready https://github.com/sample-owner/target-repo/pull/161
                                   ^^^^^^^^^^^^ ^^^^^^^^^^^      ^^^
                                   owner        repo            number
                                                -> PR_URL_OWNER_REPO_NUMBER_PATTERN
"""

GH_PR_READY_ANCHOR_PATTERN: str = r"\bgh\s+pr\s+ready\b(?![^&|;\n]*--undo)"

COMMAND_SEPARATOR_PATTERN: str = r"&&|\|\||;|\||\n|&"

BASH_LINE_CONTINUATION_PATTERN: str = r"\\\r?\n[ \t]*"

PR_URL_OWNER_REPO_NUMBER_PATTERN: str = (
    r"https?://[^/]+/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/pull/(?P<number>\d+)"
)

REPO_OVERRIDE_FLAG_PATTERN: str = (
    r"(?:^|\s)(?:--repo(?:=|\s+)|-R(?:=|\s+)?)"
    r"(?:https?://[^/\s]+/|git@[^:\s]+:|(?:[\w.-]+/)*)"
    r"(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)"
)

ALL_GH_PR_VIEW_NUMBER_COMMAND: tuple[str, ...] = (
    "gh",
    "pr",
    "view",
    "--json",
    "number",
    "--jq",
    ".number",
)
GH_REPO_FLAG: str = "--repo"
REPO_SLUG_TEMPLATE: str = "{owner}/{repo}"
