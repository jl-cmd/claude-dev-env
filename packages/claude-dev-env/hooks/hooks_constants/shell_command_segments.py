"""Shared shell-command segment helpers for Bash PreToolUse blockers.

Tokenizes a command into simple-command segments on control operators and finds
each segment's effective leading program after env assignments and launcher
wrappers. NAS ssh enforcement and unscoped-search blocking both need this
shape, so one module owns it.
"""

from __future__ import annotations

import re

__all__ = [
    "ALL_LAUNCHER_WRAPPER_COMMANDS",
    "ALL_SHELL_CONTROL_OPERATOR_TOKENS",
    "CONTROL_OPERATOR_SPLIT_PATTERN",
    "LEADING_ASSIGNMENT_PATTERN",
    "LAUNCHER_DURATION_PATTERN",
    "token_basename",
    "split_into_segments",
    "effective_leading_program",
]

ALL_LAUNCHER_WRAPPER_COMMANDS: frozenset[str] = frozenset(
    {"timeout", "nohup", "nice", "stdbuf", "setsid", "env"}
)
ALL_SHELL_CONTROL_OPERATOR_TOKENS: frozenset[str] = frozenset(
    {"&&", "||", ";", "|", "&", "|&"}
)
CONTROL_OPERATOR_SPLIT_PATTERN = re.compile(r"(&&|\|\||;|\|&|\||(?<!>)&(?!>))")
LEADING_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LAUNCHER_DURATION_PATTERN = re.compile(r"^\d+[a-z]*$", re.IGNORECASE)


def token_basename(token: str) -> str:
    """Return the lowercased basename of a path-or-command token."""
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def split_into_segments(all_command_tokens: list[str]) -> list[list[str]]:
    """Split tokens into simple-command segments on shell control operators.

    Glued operators on a single token are exploded first, then the stream is
    cut on ``&&`` / ``||`` / ``;`` / ``|`` / ``&`` / ``|&``.
    """
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


def effective_leading_program(all_segment_tokens: list[str]) -> str | None:
    """Return the effective program token after assignments and launcher wrappers.

    Skips ``VAR=value`` prefixes and known launchers (``timeout``, ``env``, …)
    plus their flags and duration arguments. Returns None when no program token
    remains.
    """
    has_seen_launcher_wrapper = False
    for each_token in all_segment_tokens:
        if LEADING_ASSIGNMENT_PATTERN.match(each_token):
            continue
        if token_basename(each_token) in ALL_LAUNCHER_WRAPPER_COMMANDS:
            has_seen_launcher_wrapper = True
            continue
        if has_seen_launcher_wrapper and (
            each_token.startswith("-") or LAUNCHER_DURATION_PATTERN.match(each_token)
        ):
            continue
        return each_token
    return None
