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
ALL_BASH_AND_POWERSHELL_TOOL_NAMES: frozenset[str] = frozenset(
    {BASH_TOOL_NAME, POWERSHELL_TOOL_NAME}
)


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


ALL_BASH_HOSTED_HOOK_ENTRIES: tuple[BashHostedHookEntry, ...] = ()
