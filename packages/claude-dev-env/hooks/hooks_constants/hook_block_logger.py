"""Shared fail-safe logger for hook block events.

Every blocking hook calls log_hook_block at the moment it decides to block,
so the user has a single log showing what tripped and why.
"""

import datetime
import json
from pathlib import Path

_HOOK_BLOCKS_LOG_RELATIVE_PATH = ".claude/logs/hook-blocks.log"
_MAX_PREVIEW_LENGTH = 500


def log_hook_block(
    calling_hook_name: str,
    hook_event: str,
    block_reason: str,
    tool_name: str | None = None,
    offending_input_preview: str | None = None,
) -> None:
    """Append one JSON record to the hook-blocks log for a block decision.

    Creates the logs directory if absent. Skips logging when the home directory
    cannot be resolved, and silently swallows all IO errors otherwise, so a
    logging failure never changes a hook's decision.

    Args:
        calling_hook_name: The script basename of the hook that is blocking.
        hook_event: The hook event type, e.g. ``PreToolUse`` or ``Stop``.
        block_reason: The human-readable reason the hook is blocking.
        tool_name: The Claude tool name when available, e.g. ``Bash``.
        offending_input_preview: A short excerpt of the input that triggered
            the block; truncated to 500 characters before writing.
    """
    try:
        home_directory = Path.home()
    except RuntimeError:
        return

    try:
        log_path = home_directory / _HOOK_BLOCKS_LOG_RELATIVE_PATH
        log_path.parent.mkdir(parents=True, exist_ok=True)

        log_record: dict[str, str] = {
            "timestamp": datetime.datetime.now().isoformat(),
            "hook": calling_hook_name,
            "event": hook_event,
            "reason": block_reason,
        }
        if tool_name is not None:
            log_record["tool"] = tool_name
        if offending_input_preview is not None:
            log_record["preview"] = offending_input_preview[:_MAX_PREVIEW_LENGTH]

        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(log_record) + "\n")
    except OSError:
        pass
