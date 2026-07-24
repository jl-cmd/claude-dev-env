"""Constants for the unscoped-search PreToolUse Bash/PowerShell blocker.

Holds tool names, program basenames, Get-ChildItem option sets, unscoped root
patterns, the shared flag/value token stride, and the deny message. Find global
option flags reuse ``destructive_command_segment_constants`` so both find
parsers stay on one set.
"""

from __future__ import annotations

import re

from hooks_constants.destructive_command_segment_constants import (
    ALL_FIND_GLOBAL_OPTION_FLAGS_TAKING_A_VALUE,
    ALL_FIND_GLOBAL_OPTION_FLAGS_WITHOUT_VALUE,
    FIND_OPTIMIZATION_LEVEL_OPTION_PREFIX,
)

__all__ = [
    "BASH_TOOL_NAME",
    "POWERSHELL_TOOL_NAME",
    "ALL_SUPPORTED_TOOL_NAMES",
    "ALL_FIND_PROGRAM_BASENAMES",
    "ALL_POWERSHELL_LISTING_PROGRAM_BASENAMES",
    "ALL_UNIX_LS_PROGRAM_BASENAMES",
    "ALL_LISTING_PROGRAM_BASENAMES",
    "ALL_FIND_GLOBAL_OPTION_FLAGS_WITHOUT_VALUE",
    "ALL_FIND_GLOBAL_OPTION_FLAGS_TAKING_A_VALUE",
    "FIND_OPTIMIZATION_LEVEL_OPTION_PREFIX",
    "FLAG_AND_VALUE_TOKEN_STRIDE",
    "ALL_FIND_EXPRESSION_INTRODUCER_TOKENS",
    "ALL_POWERSHELL_RECURSE_FLAGS",
    "ALL_UNIX_LS_RECURSE_FLAGS",
    "ALL_POWERSHELL_RECURSE_FLAG_PREFIXES",
    "ALL_POWERSHELL_PATH_FLAGS",
    "ALL_POWERSHELL_PATH_FLAG_PREFIXES",
    "ALL_TRUTHY_RECURSE_COLON_VALUES",
    "ALL_STRING_EXECUTING_SHELL_BASENAMES",
    "ALL_STRING_EXEC_COMMAND_FLAGS",
    "ALL_UNSCOPED_HOME_LITERALS",
    "ALL_UNSCOPED_HOME_LITERALS_CASEFOLD",
    "GIT_BASH_DRIVE_ROOT_PATTERN",
    "WINDOWS_DRIVE_ROOT_PATTERN",
    "POSIX_ROOT_ALIAS_PATTERN",
    "HOOK_EVENT_NAME",
    "DENY_DECISION",
    "CALLING_HOOK_NAME",
    "CORRECTIVE_MESSAGE",
]

BASH_TOOL_NAME = "Bash"
POWERSHELL_TOOL_NAME = "PowerShell"
ALL_SUPPORTED_TOOL_NAMES: frozenset[str] = frozenset(
    {BASH_TOOL_NAME, POWERSHELL_TOOL_NAME}
)

ALL_FIND_PROGRAM_BASENAMES: frozenset[str] = frozenset({"find", "find.exe"})
ALL_POWERSHELL_LISTING_PROGRAM_BASENAMES: frozenset[str] = frozenset(
    {"get-childitem", "gci", "dir"}
)
ALL_UNIX_LS_PROGRAM_BASENAMES: frozenset[str] = frozenset({"ls", "ls.exe"})
ALL_LISTING_PROGRAM_BASENAMES: frozenset[str] = (
    ALL_POWERSHELL_LISTING_PROGRAM_BASENAMES | ALL_UNIX_LS_PROGRAM_BASENAMES
)

FLAG_AND_VALUE_TOKEN_STRIDE = 2
ALL_FIND_EXPRESSION_INTRODUCER_TOKENS: frozenset[str] = frozenset({"!", "(", ")"})

ALL_POWERSHELL_RECURSE_FLAGS: frozenset[str] = frozenset(
    {"-recurse", "-r", "-rec", "/s"}
)
ALL_UNIX_LS_RECURSE_FLAGS: frozenset[str] = frozenset({"-R", "--recursive"})
ALL_POWERSHELL_RECURSE_FLAG_PREFIXES: tuple[str, ...] = (
    "-recurse:",
    "-r:",
)
ALL_POWERSHELL_PATH_FLAGS: frozenset[str] = frozenset(
    {"-path", "-literalpath", "-lp"}
)
ALL_POWERSHELL_PATH_FLAG_PREFIXES: tuple[str, ...] = (
    "-path:",
    "-literalpath:",
    "-lp:",
)
ALL_TRUTHY_RECURSE_COLON_VALUES: frozenset[str] = frozenset(
    {"$true", "true", "1", "yes", "on"}
)

ALL_STRING_EXECUTING_SHELL_BASENAMES: frozenset[str] = frozenset(
    {
        "bash",
        "bash.exe",
        "sh",
        "sh.exe",
        "pwsh",
        "pwsh.exe",
        "powershell",
        "powershell.exe",
    }
)
ALL_STRING_EXEC_COMMAND_FLAGS: frozenset[str] = frozenset(
    {"-c", "-lc", "-command", "-encodedcommand"}
)

ALL_UNSCOPED_HOME_LITERALS: frozenset[str] = frozenset(
    {
        "~",
        "~/",
        "~\\",
        "$HOME",
        "$HOME/",
        "$HOME\\",
        "${HOME}",
        "${HOME}/",
        "${HOME}\\",
        "%USERPROFILE%",
        "%USERPROFILE%\\",
        "%USERPROFILE%/",
        "$env:USERPROFILE",
        "$env:USERPROFILE\\",
        "$env:USERPROFILE/",
        "$env:HOME",
        "$env:HOME\\",
        "$env:HOME/",
    }
)
ALL_UNSCOPED_HOME_LITERALS_CASEFOLD: frozenset[str] = frozenset(
    each_literal.casefold() for each_literal in ALL_UNSCOPED_HOME_LITERALS
)

GIT_BASH_DRIVE_ROOT_PATTERN = re.compile(r"^/[a-zA-Z]/?$")
WINDOWS_DRIVE_ROOT_PATTERN = re.compile(r"^[a-zA-Z]:[\\/]*$")
POSIX_ROOT_ALIAS_PATTERN = re.compile(r"^/(?:\.|/)*$")

HOOK_EVENT_NAME = "PreToolUse"
DENY_DECISION = "deny"
CALLING_HOOK_NAME = "unscoped_search_blocker.py"

CORRECTIVE_MESSAGE = (
    "Unscoped filesystem search blocked. Never start find/Get-ChildItem at `/`, "
    "a drive root (`/c`, `C:\\`), or bare home (`~`, `$HOME`). Scope the walk to a "
    "project or worktree path (for example `find . -name '*.py'` or "
    "`find packages/claude-dev-env -iname code_rules_gate.py`). On Windows prefer "
    "es.exe with a path scope, or the Grep/Glob tools. Batch shell work; avoid "
    "parallel full-tree searches that contend for the shell and lock the host."
)
