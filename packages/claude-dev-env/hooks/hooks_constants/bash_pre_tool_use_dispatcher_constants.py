"""Constants for the Bash and PowerShell PreToolUse dispatcher.

Holds the permission outcomes, the two tool-name sets, and the ordered hosted-hook
roster with each hook's applicable-tool set. The dispatcher imports these to
select and run the hooks that a Bash or PowerShell tool call fires.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "DENY_DECISION",
    "ASK_DECISION",
    "ALLOW_DECISION",
    "HOOK_EVENT_NAME",
    "REASON_JOIN_SEPARATOR",
    "CONTEXT_JOIN_SEPARATOR",
    "BASH_TOOL_NAME",
    "POWERSHELL_TOOL_NAME",
    "ALL_BASH_ONLY_TOOL_NAMES",
    "ALL_BASH_AND_POWERSHELL_TOOL_NAMES",
    "BashHostedHookEntry",
    "ALL_BASH_HOSTED_HOOK_ENTRIES",
]

DENY_DECISION = "deny"
ASK_DECISION = "ask"
ALLOW_DECISION = "allow"
HOOK_EVENT_NAME = "PreToolUse"
REASON_JOIN_SEPARATOR = " | "
CONTEXT_JOIN_SEPARATOR = "\n"

BASH_TOOL_NAME = "Bash"
POWERSHELL_TOOL_NAME = "PowerShell"

ALL_BASH_ONLY_TOOL_NAMES: frozenset[str] = frozenset({BASH_TOOL_NAME})
ALL_BASH_AND_POWERSHELL_TOOL_NAMES: frozenset[str] = frozenset({BASH_TOOL_NAME, POWERSHELL_TOOL_NAME})


@dataclass(frozen=True)
class BashHostedHookEntry:
    """A single hosted hook with the tool names it applies to.

    Attributes:
        script_relative_path: Hook path relative to the hooks/ directory.
        applicable_tool_names: Tool names this hook runs for. The dispatcher
            skips the hook when the payload's tool is not in this set.
    """

    script_relative_path: str
    applicable_tool_names: frozenset[str]


ALL_BASH_HOSTED_HOOK_ENTRIES: tuple[BashHostedHookEntry, ...] = (
    BashHostedHookEntry("blocking/es_exe_path_rewriter.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry(
        "policy/guards/find_filesystem_walk_blocker.py",
        ALL_BASH_AND_POWERSHELL_TOOL_NAMES,
    ),
    BashHostedHookEntry("blocking/destructive_command_blocker.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/gh_body_arg_blocker.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/nas_ssh_binary_enforcer.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/volatile_path_in_post_blocker.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry(
        "blocking/pii_prevention_blocker.py", ALL_BASH_AND_POWERSHELL_TOOL_NAMES
    ),
    BashHostedHookEntry("blocking/conventional_pr_title_gate.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/reviewer_spawn_gate.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/block_main_commit.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/precommit_code_rules_gate.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/session_edit_stage_gate.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/pr_description_enforcer.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/test_preflight_check.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/convergence_gate_blocker.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/windows_rmtree_blocker.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/gh_pr_author_enforcer.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("blocking/verified_commit_gate.py", ALL_BASH_AND_POWERSHELL_TOOL_NAMES),
    BashHostedHookEntry(
        "blocking/verdict_directory_write_blocker.py", ALL_BASH_AND_POWERSHELL_TOOL_NAMES
    ),
    BashHostedHookEntry("blocking/code_review_push_gate.py", ALL_BASH_AND_POWERSHELL_TOOL_NAMES),
    BashHostedHookEntry(
        "blocking/code_review_pr_create_gate.py", ALL_BASH_AND_POWERSHELL_TOOL_NAMES
    ),
    BashHostedHookEntry(
        "blocking/code_review_stamp_directory_write_blocker.py",
        ALL_BASH_AND_POWERSHELL_TOOL_NAMES,
    ),
)
