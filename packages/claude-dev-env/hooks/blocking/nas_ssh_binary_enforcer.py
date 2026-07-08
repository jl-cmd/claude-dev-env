#!/usr/bin/env python3
"""PreToolUse hook: force the Windows OpenSSH binary for NAS ssh/scp/sftp commands.

Root cause: Git Bash's MSYS ssh reads ``~/.ssh/id_ed25519`` as world-readable
through its ACL mapping, rejects the key as "bad permissions", offers no key, and
falls back to an interactive password prompt that hangs unattended agent sessions.
The Windows OpenSSH binary under ``System32/OpenSSH`` authenticates the same key
without prompting.

Detection strategy: this hook fires only on the Bash tool. The command is
shlex-tokenized (quotes removed), glued shell control operators are exploded off
the tokens, and the tokens are split into simple-command segments on ``&&`` /
``||`` / ``;`` / ``|&`` / ``|`` / ``&``. For each segment the effective leading program is
found by skipping ``VAR=value`` assignments and launcher wrappers (``timeout``,
``nohup``, ``nice``, ``stdbuf``, ``setsid``, ``env``) with their flags and duration
arguments. A segment is evaluated only when its leading program's basename is
``ssh``/``scp``/``sftp`` (with or without a ``.exe`` suffix) AND a token in that same
segment holds the NAS address ``192.168.1.100`` as a whole-address match.

An evaluated segment is DENIED with the binary-swap message when its leading program
is a bare ssh-family word rather than a path ending in ``OpenSSH/ssh.exe`` (or
``scp.exe`` / ``sftp.exe``). An evaluated segment whose leading program is that full
OpenSSH path is DENIED with the batch-mode message when no token in the segment
carries ``BatchMode=yes``, so an authentication regression fails loudly rather than
prompting. Everything else is allowed: ssh to any other host, the full OpenSSH path
with ``BatchMode=yes``, non-Bash tools, a command that only mentions the address
without an ssh-family leading program, and a command shlex cannot tokenize.
"""

import json
import shlex
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.nas_ssh_binary_enforcer_constants import (  # noqa: E402
    ALL_LAUNCHER_WRAPPER_COMMANDS,
    ALL_OPENSSH_BINARY_PATH_SUFFIXES,
    ALL_SHELL_CONTROL_OPERATOR_TOKENS,
    ALL_SSH_FAMILY_COMMAND_BASENAMES,
    BARE_SSH_BINARY_MESSAGE,
    BASH_TOOL_NAME,
    BATCH_MODE_PATTERN,
    CONTROL_OPERATOR_SPLIT_PATTERN,
    LAUNCHER_DURATION_PATTERN,
    LEADING_ASSIGNMENT_PATTERN,
    MISSING_BATCH_MODE_MESSAGE,
    NAS_ADDRESS_PATTERN,
)


def _token_basename(token: str) -> str:
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _is_openssh_binary_path(token: str) -> bool:
    normalized_token = token.replace("\\", "/").lower()
    return any(
        normalized_token.endswith(each_suffix)
        for each_suffix in ALL_OPENSSH_BINARY_PATH_SUFFIXES
    )


def _split_into_segments(all_command_tokens: list[str]) -> list[list[str]]:
    all_exploded_tokens: list[str] = []
    for each_token in all_command_tokens:
        for each_fragment in CONTROL_OPERATOR_SPLIT_PATTERN.split(each_token):
            if each_fragment:
                all_exploded_tokens.append(each_fragment)
    all_segments: list[list[str]] = []
    current_segment: list[str] = []
    for each_token in all_exploded_tokens:
        if each_token in ALL_SHELL_CONTROL_OPERATOR_TOKENS:
            all_segments.append(current_segment)
            current_segment = []
            continue
        current_segment.append(each_token)
    all_segments.append(current_segment)
    return all_segments


def _effective_leading_program(all_segment_tokens: list[str]) -> str | None:
    has_seen_launcher_wrapper = False
    for each_token in all_segment_tokens:
        if LEADING_ASSIGNMENT_PATTERN.match(each_token):
            continue
        if _token_basename(each_token) in ALL_LAUNCHER_WRAPPER_COMMANDS:
            has_seen_launcher_wrapper = True
            continue
        if has_seen_launcher_wrapper and (
            each_token.startswith("-") or LAUNCHER_DURATION_PATTERN.match(each_token)
        ):
            continue
        return each_token
    return None


def _segment_references_nas(all_segment_tokens: list[str]) -> bool:
    return any(NAS_ADDRESS_PATTERN.search(each_token) for each_token in all_segment_tokens)


def _segment_carries_batch_mode(all_segment_tokens: list[str]) -> bool:
    return any(BATCH_MODE_PATTERN.search(each_token) for each_token in all_segment_tokens)


def _find_nas_ssh_violation(command: str) -> str | None:
    """Return the deny message for a NAS ssh-family command, or None to allow.

    ::

        ssh -p 9222 jon@192.168.1.100 "ls"          flag: bare-binary message
        "…/OpenSSH/ssh.exe" -p 9222 jon@192.168…    flag: missing-batch-mode message
        "…/OpenSSH/ssh.exe" -o BatchMode=yes …NAS   ok:   None
        ssh jon@example.com "ls"                     ok:   None

    Tokenizes the command, splits it into simple-command segments, and evaluates
    each segment whose leading program is an ssh-family word AND whose tokens carry
    the NAS address. A bare ssh-family leader returns the binary-swap message; the
    full OpenSSH path leader without a ``BatchMode=yes`` token returns the batch-mode
    message. Returns None when shlex cannot tokenize the command.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        The deny message string when a segment violates the NAS ssh policy, else None.
    """
    try:
        all_command_tokens = shlex.split(command)
    except ValueError:
        return None
    for each_segment in _split_into_segments(all_command_tokens):
        leading_program = _effective_leading_program(each_segment)
        if leading_program is None:
            continue
        if _token_basename(leading_program) not in ALL_SSH_FAMILY_COMMAND_BASENAMES:
            continue
        if not _segment_references_nas(each_segment):
            continue
        if not _is_openssh_binary_path(leading_program):
            return BARE_SSH_BINARY_MESSAGE
        if not _segment_carries_batch_mode(each_segment):
            return MISSING_BATCH_MODE_MESSAGE
    return None


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != BASH_TOOL_NAME:
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    deny_reason = _find_nas_ssh_violation(command)
    if deny_reason is None:
        sys.exit(0)

    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    log_hook_block(
        calling_hook_name="nas_ssh_binary_enforcer.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
        tool_name=tool_name,
        offending_input_preview=command,
    )
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
