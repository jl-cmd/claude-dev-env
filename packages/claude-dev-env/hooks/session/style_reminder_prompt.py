#!/usr/bin/env python3
"""UserPromptSubmit hook. Adds the style reminder to every message.

::

    user sends a message
             |
             v
    UserPromptSubmit fires -> additionalContext: "small words. few words. always. forever."
             |
             v
    the model sees the reminder this turn, and each turn after

Claude Code and Codex CLI both read the same ``additionalContext`` shape on
their ``UserPromptSubmit`` event. One script serves both. The hook prints
text and stops.
"""

from __future__ import annotations

import json
import sys

import _path_setup  # noqa: F401

from hooks_constants.style_reminder_prompt_constants import STYLE_REMINDER_PROMPT


def main() -> None:
    """Print the style reminder as UserPromptSubmit additionalContext."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": STYLE_REMINDER_PROMPT,
        }
    }
    sys.stdout.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    main()
