"""Constants for the PR done-checklist context reminder.

The reminder is a PostToolUse observer on Bash and PowerShell. It never
blocks. After a successful ``git push`` or ``gh pr create`` it probes the
branch's pull request through ``gh`` and adds one checklist to context.
"""

from __future__ import annotations

__all__ = [
    "GIT_PROGRAM_NAME",
    "GIT_PUSH_SUBCOMMAND",
    "GH_PROGRAM_NAME",
    "GH_PR_SUBCOMMAND",
    "GH_PR_CREATE_ACTION",
    "ALL_GIT_OPTIONS_WITH_VALUE",
    "ALL_POWERSHELL_PROGRAM_NAMES",
    "ALL_POWERSHELL_COMMAND_FLAGS",
    "ALL_GH_PR_VIEW_ARGUMENTS",
    "GH_PR_VIEW_TIMEOUT_SECONDS",
    "NO_PULL_REQUEST_MARKER",
    "EXIT_CODE_ERROR_PREFIX",
    "DONE_LABEL_NAME",
    "MERGEABLE_CLEAN_VALUE",
    "MERGEABLE_CONFLICTING_VALUE",
    "MERGEABLE_UNKNOWN_VALUE",
    "ALL_FAILING_CHECK_CONCLUSIONS",
    "ALL_PASSING_CHECK_CONCLUSIONS",
    "CHECK_COMPLETED_STATUS",
    "STATUS_CONTEXT_STATE_KEY",
    "REMINDER_HEADER",
    "REMINDER_FOOTER",
    "REMINDER_LINE_SEPARATOR",
    "ALL_REMINDER_HINTS_BY_MERGEABLE",
    "VERDICT_DONE",
    "VERDICT_NOT_DONE",
    "NO_PULL_REQUEST_REMINDER",
    "RECHECK_COMMAND_TEMPLATE",
    "ADD_LABEL_COMMAND_TEMPLATE",
]

GIT_PROGRAM_NAME: str = "git"
GIT_PUSH_SUBCOMMAND: str = "push"
GH_PROGRAM_NAME: str = "gh"
GH_PR_SUBCOMMAND: str = "pr"
GH_PR_CREATE_ACTION: str = "create"
ALL_GIT_OPTIONS_WITH_VALUE: frozenset[str] = frozenset({"-C", "-c"})
ALL_POWERSHELL_PROGRAM_NAMES: frozenset[str] = frozenset(
    {"pwsh", "pwsh.exe", "powershell", "powershell.exe"}
)
ALL_POWERSHELL_COMMAND_FLAGS: frozenset[str] = frozenset({"-command", "-c"})

ALL_GH_PR_VIEW_ARGUMENTS: tuple[str, ...] = (
    "gh",
    "pr",
    "view",
    "--json",
    "number,url,isDraft,mergeable,mergeStateStatus,statusCheckRollup,labels",
)
GH_PR_VIEW_TIMEOUT_SECONDS: int = 20
NO_PULL_REQUEST_MARKER: str = "no pull requests found"
EXIT_CODE_ERROR_PREFIX: str = "Error: Exit code "

DONE_LABEL_NAME: str = "done"

MERGEABLE_CLEAN_VALUE: str = "MERGEABLE"
MERGEABLE_CONFLICTING_VALUE: str = "CONFLICTING"
MERGEABLE_UNKNOWN_VALUE: str = "UNKNOWN"

ALL_FAILING_CHECK_CONCLUSIONS: frozenset[str] = frozenset(
    {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}
)
ALL_PASSING_CHECK_CONCLUSIONS: frozenset[str] = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
CHECK_COMPLETED_STATUS: str = "COMPLETED"
STATUS_CONTEXT_STATE_KEY: str = "state"

REMINDER_HEADER: str = "=== PR DONE CHECKLIST (context reminder, never a block) ==="
REMINDER_FOOTER: str = "A PR is done only when every line above is clean."
REMINDER_LINE_SEPARATOR: str = "\n"
ALL_REMINDER_HINTS_BY_MERGEABLE: dict[str, str] = {
    MERGEABLE_CLEAN_VALUE: "no conflicts with the base branch",
    MERGEABLE_CONFLICTING_VALUE: (
        "CONFLICTS with the base branch. Merge origin/main into this branch, "
        "resolve every conflict, run the tests, push again."
    ),
    MERGEABLE_UNKNOWN_VALUE: "GitHub is still computing. Re-run the re-check command in a minute.",
}
VERDICT_DONE: str = "DONE. Add the label now:"
VERDICT_NOT_DONE: str = "NOT DONE. Do not add the done label yet."
NO_PULL_REQUEST_REMINDER: str = (
    "=== PR DONE CHECKLIST (context reminder, never a block) ===\n"
    "No open pull request found for this branch. Open a draft PR with gh pr create --draft.\n"
    "A branch is done only when its PR has clean CI, no merge conflicts, and the done label."
)
RECHECK_COMMAND_TEMPLATE: str = (
    "gh pr view {number} --json mergeable,mergeStateStatus,statusCheckRollup,labels"
)
ADD_LABEL_COMMAND_TEMPLATE: str = "gh pr edit {number} --add-label {label}"
