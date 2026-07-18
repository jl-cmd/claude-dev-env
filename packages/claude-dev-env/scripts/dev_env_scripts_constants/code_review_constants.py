"""Named constants for the host-aware `/code-review` invoker.

`invoke_code_review.py` imports every scalar and structural constant it
needs from this module (and shared flag tokens from
`grok_worker_constants`) so the prompt, model alias, and JSON keys are
never hardcoded twice.
"""

from __future__ import annotations

CODE_REVIEW_SLASH_COMMAND: str = "/code-review"
"""Built-in Claude Code slash command that runs the repository review."""

CODE_REVIEW_EFFORT: str = "xhigh"
"""Effort level passed to the built-in review slash command."""

CODE_REVIEW_FIX_FLAG: str = "--fix"
"""Slash-command flag that applies automatic fixes for review findings."""

CODE_REVIEW_PROMPT: str = (
    f"{CODE_REVIEW_SLASH_COMMAND} {CODE_REVIEW_EFFORT} {CODE_REVIEW_FIX_FLAG}"
)
"""Single-turn prompt that runs the built-in review slash command with fixes."""

CODE_REVIEW_MODEL_ALIAS: str = "opus"
"""CLI `--model` short alias the review always pins to."""

PERMISSION_MODE_FLAG: str = "--permission-mode"
"""CLI flag that selects how the headless claude process handles tool permission prompts."""

PERMISSION_MODE_BYPASS: str = "bypassPermissions"
"""Permission-mode value that auto-approves tools for unattended chain runs."""

MODE_IN_SESSION: str = "in_session"
"""Result mode when the host is Claude and the session already runs opus."""

MODE_CHAIN: str = "chain"
"""Result mode when the helper spawns a headless claude chain for the review."""

RESULT_KEY_MODE: str = "mode"
"""JSON result key naming the review mode (`in_session` or `chain`)."""

RESULT_KEY_SERVED_COMMAND: str = "served_command"
"""JSON result key naming the chain binary that served the call, or null."""

RESULT_KEY_RETURNCODE: str = "returncode"
"""JSON result key holding the process return code from the chain run."""

RESULT_KEY_DIRTY_TREE: str = "dirty_tree"
"""JSON result key holding whether the working tree is dirty after the review."""

CLI_SESSION_MODEL_FLAG: str = "--session-model"
"""CLI flag naming the caller's current session model short alias."""

GIT_BINARY: str = "git"
"""Executable name resolved on PATH for working-tree dirty checks."""

GIT_STATUS_SUBCOMMAND: str = "status"
"""Git subcommand used to detect an uncommitted dirty working tree."""

GIT_PORCELAIN_FLAG: str = "--porcelain"
"""Git status flag that prints machine-readable dirty-path lines."""

IN_SESSION_RETURNCODE: int = 0
"""Return code reported when the helper hands the review back to the in-session skill."""

HOST_PROFILE_ERROR_RETURNCODE: int = 1
"""Return code when host-profile detection raises ValueError at the CLI boundary."""

SUCCESSFUL_REVIEW_RETURNCODE: int = 0
"""Return code required before a clean stamp may advance past CODE_REVIEW."""

SUBPROCESS_ENCODING_KEYWORD: str = "encoding"
"""Keyword name for text encoding when forwarding chain subprocess runner kwargs."""

SUBPROCESS_ERRORS_KEYWORD: str = "errors"
"""Keyword name for text decode error policy when forwarding chain subprocess runner kwargs."""

ALL_SUBPROCESS_TEXT_CODEC_KEYWORDS: tuple[str, ...] = (
    SUBPROCESS_ENCODING_KEYWORD,
    SUBPROCESS_ERRORS_KEYWORD,
)
"""Keyword names to forward from the chain runner for text-mode subprocess capture."""
