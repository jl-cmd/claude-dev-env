"""Shared stdout emitter for PostToolUse hooks that add context."""

from __future__ import annotations

import json
import sys

from hooks_constants.bash_post_call_dispatcher_constants import (
    ADDITIONAL_CONTEXT_KEY,
    HOOK_EVENT_NAME_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    POST_TOOL_USE_HOOK_EVENT_NAME,
)


def write_post_tool_use_context_to_stdout(context_text: str) -> None:
    """Write one PostToolUse additionalContext payload to stdout.

    A hosted hook writes its note here and the Bash PostToolUse dispatcher
    reads it back, joins it with the other hooks' notes, and writes the joined
    text here in turn. Both ends of that hop share this one payload shape
    rather than each carrying a copy of it.

    Args:
        context_text: The advisory text the dispatcher forwards.
    """
    payload = {
        HOOK_SPECIFIC_OUTPUT_KEY: {
            HOOK_EVENT_NAME_KEY: POST_TOOL_USE_HOOK_EVENT_NAME,
            ADDITIONAL_CONTEXT_KEY: context_text,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
