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
    "BLOCKED [shell-substitution]: command contains $(...), backtick, or "
    "<(...)/>(...) process substitution, which forces a permission prompt "
    "because the Claude Code allowlist matcher does not descend into "
    "substitutions.\n\n"
    "Fix: split into two Bash tool calls, or rewrite without substitution.\n"
    '  cd X && echo "$(git rev-parse HEAD)"\n'
    "becomes either two calls:\n"
    "  1) cd X\n"
    "  2) git rev-parse HEAD\n"
    "or one substitution-free call:\n"
    "  git -C X rev-parse HEAD\n\n"
    "Process substitution example:\n"
    "  diff <(cat a) <(cat b)\n"
    "becomes two separate Bash calls to `cat a` and `cat b`, with the diff "
    "performed on the captured outputs.\n\n"
    "See `shell-invocation.md` in the rules directory for full guidance."
)
