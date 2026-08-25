"""Constants for the Cursor-vs-Python gate misfire PreToolUse blocker.

Blocks Shell commands that launch Cursor's CLI or GUI binary against a Python
script with code-rules-gate flags. That path feeds unknown options into
Cursor's main process ``resolveArgs``, where ``console.warn`` on a closed pipe
raises an EPIPE error dialog and still opens the script as an editor path.
"""

from __future__ import annotations

import re

__all__ = [
    "ALL_SUPPORTED_TOOL_NAMES",
    "BASH_TOOL_NAME",
    "POWERSHELL_TOOL_NAME",
    "TOOL_NAME_KEY",
    "TOOL_INPUT_KEY",
    "COMMAND_KEY",
    "HOOK_SPECIFIC_OUTPUT_KEY",
    "HOOK_EVENT_NAME_KEY",
    "HOOK_EVENT_NAME",
    "PERMISSION_DECISION_KEY",
    "DENY_DECISION",
    "PERMISSION_DECISION_REASON_KEY",
    "CALLING_HOOK_NAME",
    "CURSOR_LAUNCH_PATTERN",
    "GATE_SCRIPT_PATTERN",
    "GATE_FLAG_PATTERN",
    "PYTHON_PATH_PATTERN",
    "CORRECTIVE_MESSAGE",
]

BASH_TOOL_NAME = "Bash"
POWERSHELL_TOOL_NAME = "PowerShell"
ALL_SUPPORTED_TOOL_NAMES: frozenset[str] = frozenset(
    {BASH_TOOL_NAME, POWERSHELL_TOOL_NAME}
)

TOOL_NAME_KEY = "tool_name"
TOOL_INPUT_KEY = "tool_input"
COMMAND_KEY = "command"

HOOK_SPECIFIC_OUTPUT_KEY = "hookSpecificOutput"
HOOK_EVENT_NAME_KEY = "hookEventName"
HOOK_EVENT_NAME = "PreToolUse"
PERMISSION_DECISION_KEY = "permissionDecision"
DENY_DECISION = "deny"
PERMISSION_DECISION_REASON_KEY = "permissionDecisionReason"

CALLING_HOOK_NAME = "cursor_cli_python_misfire_blocker.py"

CURSOR_LAUNCH_PATTERN = re.compile(
    r"(?i)"
    r"(?:"
    r"(?:^|[\s;&|])(?:cursor(?:\.cmd|\.exe)?)(?=\s|[\"']|$)"
    r"|"
    r"[\\/](?:cursor(?:\.cmd|\.exe)?)(?=\s|[\"']|$)"
    r")"
)
GATE_SCRIPT_PATTERN = re.compile(r"(?i)code_rules_gate\.py\b")
GATE_FLAG_PATTERN = re.compile(
    r"(?i)(?:^|[\s,\"'])(?:--base|--staged|--repo-root|--only-under)"
    r"(?:\s|=|$|[\"'])"
)
PYTHON_PATH_PATTERN = re.compile(r"(?i)\.py(?:\s|$|['\":])")

CORRECTIVE_MESSAGE = (
    "BLOCKED [cursor-python-misfire]: Cursor's CLI/GUI was invoked against a "
    "Python script with code-rules-gate flags. Cursor treats those flags as "
    "unknown options, warns on a closed pipe, and raises an EPIPE error dialog "
    "while still opening the script as an editor path.\n\n"
    "To run the gate:\n"
    "  python <path-to>/code_rules_gate.py --base origin/main\n\n"
    "To open a file on screen in its native Windows app:\n"
    "  Invoke-Item -LiteralPath '<path>'\n\n"
    "Do not pass --base, --staged, --repo-root, or --only-under to cursor / "
    "Cursor.exe."
)
