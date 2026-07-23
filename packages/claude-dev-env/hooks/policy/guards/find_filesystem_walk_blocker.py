#!/usr/bin/env python3
"""PreToolUse hook: block filesystem find walks and rewrite toward es.exe.

Hardens the archived find_to_everything_redirector. Matches -name, -iname, bare
find /, full-path Git usr\\bin\\find.exe launches, and find.exe anywhere in a
Bash or PowerShell command. Denies with a concrete es.exe rewrite and an
everything-search skill hint. Never rewrites in place — the agent must re-issue
the es.exe form.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.find_filesystem_walk_constants import (  # noqa: E402
    ALL_FIND_BLOCKER_TOOL_NAMES,
    BLOCK_REASON_HEADER,
    BLOCKER_HOOK_SCRIPT_NAME,
    ES_EXE_WINDOWS_QUOTED_PATH,
    ES_EXE_WSL_PATH,
    ES_REWRITE_BARE_TEMPLATE,
    ES_REWRITE_EMPTY_TERM_FALLBACK,
    EVERYTHING_SEARCH_SKILL_HINT_TEMPLATE,
    EVERYTHING_SEARCH_SKILL_NAME,
    FIND_PROGRAM_INVOCATION_PATTERN,
    HOOK_EVENT_NAME,
    NAME_SEARCH_FLAG_PATTERN,
    PERMISSION_DENY,
    POSIX_FIND_WALK_FLAG_PATTERN,
    WILDCARD_CHARACTERS_TO_STRIP,
    WINDOWS_TEXT_FIND_FLAG_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin  # noqa: E402


def command_invokes_filesystem_find(command: str) -> bool:
    """Return True when the command launches POSIX/Git find for a filesystem walk.

    ::

        command_invokes_filesystem_find('find / -name nest_asyncio.py')
        ok:   True
        flag: False for findstr, es.exe, git rev-list --find-object,
              or Windows text-find pipes like 'echo x | find /i foo'

    Args:
        command: Full Bash or PowerShell command text from the tool payload.

    Returns:
        True when a find / find.exe program token is present as a filesystem-walk
        invocation. Windows System32 text-search find (flags /i /v /c /n /off
        without POSIX walk flags) is not a walk and returns False.
    """
    if not command:
        return False
    if not FIND_PROGRAM_INVOCATION_PATTERN.search(command):
        return False
    if WINDOWS_TEXT_FIND_FLAG_PATTERN.search(command) and not (
        POSIX_FIND_WALK_FLAG_PATTERN.search(command)
    ):
        return False
    return True


def extract_name_search_term(command: str) -> str:
    """Return the -name/-iname pattern with wildcards stripped, or empty.

    Args:
        command: Full command text that may carry -name or -iname.

    Returns:
        Clean search term for es.exe, or empty string when no name flag is present.
    """
    match = NAME_SEARCH_FLAG_PATTERN.search(command)
    if match is None:
        return ""
    raw_pattern = match.group("pattern").strip("\"'")
    cleaned_term = raw_pattern
    for each_wildcard in WILDCARD_CHARACTERS_TO_STRIP:
        cleaned_term = cleaned_term.replace(each_wildcard, "")
    return cleaned_term.strip()


def _looks_like_wsl_shell_command(command: str) -> bool:
    return bool(re.search(r"(?i)(?:^|[\s;/])(?:bash|wsl|sh)(?:\.exe)?\b", command))


def choose_es_exe_path(command: str) -> str:
    """Return the WSL or Windows es.exe path form matching the shell style.

    Args:
        command: Full command text used to detect WSL/bash wrappers.

    Returns:
        Quoted Windows path, or the WSL /mnt/c form when the shell is bash/wsl.
    """
    if _looks_like_wsl_shell_command(command):
        return ES_EXE_WSL_PATH
    return ES_EXE_WINDOWS_QUOTED_PATH


def build_es_rewrite_command(command: str, search_term: str) -> str:
    """Build a suggested es.exe invocation for the blocked find walk.

    Args:
        command: Original find command (used only for shell-style path choice).
        search_term: Clean name term extracted from -name/-iname, or empty.

    Returns:
        Concrete es.exe command string the agent should re-issue.
    """
    es_path = choose_es_exe_path(command)
    if not search_term:
        return ES_REWRITE_EMPTY_TERM_FALLBACK.format(es_path=es_path)
    return ES_REWRITE_BARE_TEMPLATE.format(es_path=es_path, search_term=search_term)


def build_block_reason(command: str) -> str:
    """Compose the deny reason with es.exe rewrite and skill hint.

    Args:
        command: Offending find command text.

    Returns:
        Multi-line permissionDecisionReason for the PreToolUse deny payload.
    """
    search_term = extract_name_search_term(command)
    es_rewrite = build_es_rewrite_command(command, search_term)
    skill_args = search_term if search_term else "<name-pattern>"
    skill_hint = EVERYTHING_SEARCH_SKILL_HINT_TEMPLATE.format(
        skill_name=EVERYTHING_SEARCH_SKILL_NAME,
        search_term=skill_args,
    )
    return (
        f"{BLOCK_REASON_HEADER}\n\n"
        f"Blocked command:\n  {command}\n\n"
        f"Use Bash with es.exe:\n\n"
        f"  {es_rewrite}\n\n"
        f"{skill_hint}\n\n"
        "Policy: es.exe is primary. Do not substitute drive-root "
        "Get-ChildItem -Recurse."
    )


def build_deny_payload(block_reason: str) -> dict[str, object]:
    """Return the PreToolUse deny JSON payload.

    Args:
        block_reason: Human-readable reason including the es.exe rewrite.

    Returns:
        Dict ready for json.dumps to stdout.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": PERMISSION_DENY,
            "permissionDecisionReason": block_reason,
        }
    }


def main() -> None:
    """Read stdin, deny filesystem find walks, otherwise exit allow."""
    hook_input = read_hook_input_dictionary_from_stdin()
    if hook_input is None:
        sys.exit(0)

    raw_tool_name = hook_input.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    if tool_name not in ALL_FIND_BLOCKER_TOOL_NAMES:
        sys.exit(0)

    raw_tool_input = hook_input.get("tool_input", {})
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}
    raw_command = tool_input.get("command", "")
    command = raw_command if isinstance(raw_command, str) else ""
    if not command_invokes_filesystem_find(command):
        sys.exit(0)

    block_reason = build_block_reason(command)
    log_hook_block(
        calling_hook_name=BLOCKER_HOOK_SCRIPT_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=block_reason,
        tool_name=tool_name,
        offending_input_preview=command,
    )
    print(json.dumps(build_deny_payload(block_reason)))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
