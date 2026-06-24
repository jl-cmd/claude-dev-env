"""Constants for the PostToolUse dispatcher that hosts the after-write hooks.

Holds the ordered hosted-hook list with each hook's extra command-line
arguments and blocking flag, the PostToolUse block-decision string and key,
and the hook-event name. The dispatcher imports each of these by name.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "BLOCK_DECISION",
    "DECISION_KEY",
    "REASON_KEY",
    "HOOK_EVENT_NAME",
    "EMPTY_REASON_BLOCK_FALLBACK",
    "BLOCKING_CRASH_DENY_REASON",
    "PLUGIN_ROOT_PLACEHOLDER",
    "PostHostedHookEntry",
    "ALL_POST_HOSTED_HOOK_ENTRIES",
]

BLOCK_DECISION = "block"
DECISION_KEY = "decision"
REASON_KEY = "reason"
HOOK_EVENT_NAME = "PostToolUse"
EMPTY_REASON_BLOCK_FALLBACK = "[dispatcher] hook blocked with no reason — write blocked"
BLOCKING_CRASH_DENY_REASON = "[dispatcher] hook crash in blocking hook — write blocked for safety"

PLUGIN_ROOT_PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"


@dataclass(frozen=True)
class PostHostedHookEntry:
    """A single hosted PostToolUse hook with its run-time arguments and flags.

    Attributes:
        script_relative_path: Hook path relative to the hooks/ directory.
        extra_argument_relative_paths: Command-line arguments the live entry
            passes after the script path, each a path relative to the plugin
            root (the hooks/ parent). The dispatcher resolves each to an
            absolute path and exposes them as the hook's argv tail, so a hook
            that reads sys.argv[1] resolves the same path the live entry gives
            it. An empty tuple means the live entry passes no extra arguments.
        is_blocking: True when this hook can emit a block decision and a crash
            should surface a blocking signal; False when the hook only performs
            a side effect and never blocks.
    """

    script_relative_path: str
    extra_argument_relative_paths: tuple[str, ...] = field(default_factory=tuple)
    is_blocking: bool = field(default=False)


ALL_POST_HOSTED_HOOK_ENTRIES: tuple[PostHostedHookEntry, ...] = (
    PostHostedHookEntry(
        script_relative_path="validation/mypy_validator.py",
        is_blocking=True,
    ),
    PostHostedHookEntry(
        script_relative_path="workflow/auto_formatter.py",
        is_blocking=False,
    ),
    PostHostedHookEntry(
        script_relative_path="workflow/doc_gist_auto_publish.py",
        extra_argument_relative_paths=(PLUGIN_ROOT_PLACEHOLDER,),
        is_blocking=False,
    ),
)
