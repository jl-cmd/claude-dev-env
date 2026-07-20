"""Constants for the find filesystem-walk blocker and Git find handle guard.

Shared by the PreToolUse Bash/PowerShell blocker that rewrites find walks to
es.exe, and by the process guard that stops runaway Git usr\\bin\\find.exe when
handle counts exceed the operator threshold.
"""

from __future__ import annotations

import re

BASH_TOOL_NAME = "Bash"
POWERSHELL_TOOL_NAME = "PowerShell"
ALL_FIND_BLOCKER_TOOL_NAMES: frozenset[str] = frozenset(
    {BASH_TOOL_NAME, POWERSHELL_TOOL_NAME}
)

HOOK_EVENT_NAME = "PreToolUse"
PERMISSION_DENY = "deny"

FIND_PROGRAM_INVOCATION_PATTERN = re.compile(
    r"""(?ix)
    (?:
        # find / find.exe at a command position: start of command, or right
        # after a shell separator or PowerShell call operator (optional
        # whitespace between), with an optional spaceless path prefix. A plain
        # space is NOT a command position, so the word "find" sitting inside
        # another command's arguments or a quoted message is not matched.
        (?: ^ | \|\| | && | [;&|\n(`] )
        \s*
        (?: & \s* )?
        (?: ["'] )?
        (?: [A-Za-z]: )?
        (?: [^"'`\s;&|]* [/\\] )*
        find (?: \.exe )?
        (?= [\s"'`;&|)] | $ )
      |
        # a quoted path ending in find.exe, where spaces inside the quotes are
        # allowed (e.g. "C:\Program Files\Git\usr\bin\find.exe").
        ["'] [^"'\n]* [/\\] find \.exe ["']
    )
    """
)

NAME_SEARCH_FLAG_PATTERN = re.compile(
    r"""(?ix)
    (?:-iname|-name)
    \s+
    (?P<pattern>"[^"]*"|'[^']*'|\S+)
    """
)

# Windows System32 find text-search flags (/i /v /c /n /off). A find that only
# uses these is not a filesystem walk, so the PreToolUse blocker must allow it.
WINDOWS_TEXT_FIND_FLAG_PATTERN = re.compile(
    r"""(?ix)
    find (?: \.exe )?
    \s+
    /+ (?: i | v | c | n | off ) \b
    """
)

# POSIX find walk signals. When present, the command is a filesystem walk even
# if a Windows-style slash flag also appears.
POSIX_FIND_WALK_FLAG_PATTERN = re.compile(
    r"""(?ix)
    - (?: name | iname | type | maxdepth | mindepth | path | regex | prune
        | print | exec | delete | empty | size | mtime | atime | ctime )
    \b
    """
)

WILDCARD_CHARACTERS_TO_STRIP = "*?"

ES_EXE_WINDOWS_PATH = r"C:\Program Files\Everything\es.exe"
ES_EXE_WINDOWS_QUOTED_PATH = f'"{ES_EXE_WINDOWS_PATH}"'
ES_EXE_WSL_PATH = r"/mnt/c/Program\ Files/Everything/es.exe"

EVERYTHING_SEARCH_SKILL_NAME = "everything-search"

BLOCKER_HOOK_SCRIPT_NAME = "find_filesystem_walk_blocker.py"

HANDLE_KILL_THRESHOLD = 2000

GIT_FIND_PATH_SUFFIX = r"\git\usr\bin\find.exe"
FIND_PROCESS_NAME = "find"

POWERSHELL_EXECUTABLE_NAME = "powershell.exe"
POWERSHELL_NO_PROFILE_FLAG = "-NoProfile"
POWERSHELL_COMMAND_FLAG = "-Command"

TASKKILL_EXECUTABLE_NAME = "taskkill"
TASKKILL_FORCE_FLAG = "/F"
TASKKILL_PID_FLAG = "/PID"

FIND_PROCESS_QUERY_SCRIPT = (
    "Get-CimInstance Win32_Process -Filter \"Name='find.exe'\" | "
    "ForEach-Object { "
    "$proc = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue; "
    "if ($null -eq $proc) { return }; "
    "[PSCustomObject]@{ "
    "ProcessId = $_.ProcessId; "
    "HandleCount = [int]$proc.HandleCount; "
    "ExecutablePath = [string]$_.ExecutablePath; "
    "CommandLine = [string]$_.CommandLine "
    "} "
    "} | ConvertTo-Json -Compress"
)

TOTAL_HANDLE_COUNTER_PATH = r"\Process(_Total)\Handle Count"
TOTAL_HANDLE_COUNTER_QUERY_TEMPLATE = (
    "(Get-Counter '{counter_path}').CounterSamples[0].CookedValue"
)

WATCH_POLL_INTERVAL_SECONDS = 5

GUARD_HOOK_SCRIPT_NAME = "git_find_handle_guard.py"

CLI_WATCH_FLAG = "--watch"
CLI_DRY_RUN_FLAG = "--dry-run"
CLI_THRESHOLD_FLAG = "--threshold"

CLI_DESCRIPTION_TEMPLATE = (
    "Kill Git usr\\bin\\find.exe processes whose handle count exceeds {threshold}."
)
CLI_WATCH_HELP_TEMPLATE = (
    "Poll every {poll_seconds}s and kill runaways."
)
CLI_DRY_RUN_HELP = "Report counters without terminating processes."
CLI_THRESHOLD_HELP_TEMPLATE = (
    "Handle count threshold (default {threshold})."
)

BLOCK_REASON_HEADER = (
    "BLOCKED [find-to-es]: filesystem find walks open runaway handle counts on "
    "Windows (Git usr\\bin\\find.exe has been observed past 2M handles). "
    "Use Everything Search (es.exe) instead."
)

EVERYTHING_SEARCH_SKILL_HINT_TEMPLATE = (
    "Or use the everything-search skill:\n\n"
    "  Skill(skill='{skill_name}', args='{search_term}')"
)

ES_REWRITE_BARE_TEMPLATE = "{es_path} {search_term}"
ES_REWRITE_EMPTY_TERM_FALLBACK = "{es_path} <name-pattern>"
