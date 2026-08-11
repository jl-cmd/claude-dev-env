"""Constants for the shell-substitution PreToolUse Bash blocker.

Holds the tool name, the payload keys, the four detection patterns, the deny
decision shape, and the corrective message. The hook imports these so no
single-use constant sits at its file scope.
"""

from __future__ import annotations

import re

__all__ = [
    "BASH_TOOL_NAME",
    "TOOL_NAME_KEY",
    "TOOL_INPUT_KEY",
    "COMMAND_KEY",
    "HOOK_SPECIFIC_OUTPUT_KEY",
    "HOOK_EVENT_NAME_KEY",
    "HOOK_EVENT_NAME",
    "PERMISSION_DECISION_KEY",
    "DENY_DECISION",
    "PERMISSION_DECISION_REASON_KEY",
    "DOLLAR_PAREN_PATTERN",
    "EVEN_BACKSLASH_BACKTICK_PATTERN",
    "PROCESS_SUBSTITUTION_PATTERN",
    "SINGLE_QUOTED_RUN_PATTERN",
    "STRIPPED_RUN_REPLACEMENT",
    "CORRECTIVE_MESSAGE",
]

BASH_TOOL_NAME = "Bash"

TOOL_NAME_KEY = "tool_name"
TOOL_INPUT_KEY = "tool_input"
COMMAND_KEY = "command"

HOOK_SPECIFIC_OUTPUT_KEY = "hookSpecificOutput"
HOOK_EVENT_NAME_KEY = "hookEventName"
HOOK_EVENT_NAME = "PreToolUse"
PERMISSION_DECISION_KEY = "permissionDecision"
DENY_DECISION = "deny"
PERMISSION_DECISION_REASON_KEY = "permissionDecisionReason"

DOLLAR_PAREN_PATTERN = re.compile(r"\$\((?!\()")
EVEN_BACKSLASH_BACKTICK_PATTERN = re.compile(r"(?<!\\)(?:\\\\)*`")
PROCESS_SUBSTITUTION_PATTERN = re.compile(r"[<>]\(")
SINGLE_QUOTED_RUN_PATTERN = re.compile(r"'[^']*'")
STRIPPED_RUN_REPLACEMENT = ""

CORRECTIVE_MESSAGE = (
    "BLOCKED [shell-substitution]: Split the command into two Bash calls when it "
    "contains `$(...)`, backticks, or process substitution. Use `git -C X "
    "rev-parse HEAD` for the one-call form. For process substitution, run the "
    "source commands separately and compare their captured outputs. See "
    "`shell-invocation.md` for the full contract."
)
