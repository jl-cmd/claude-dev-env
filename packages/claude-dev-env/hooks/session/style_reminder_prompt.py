#!/usr/bin/env python3
"""UserPromptSubmit hook — inject the style reminder into every message.

::

    user types a prompt
             |
             v
    UserPromptSubmit fires  ->  additionalContext: "small words. few words. always. forever."
             |
             v
    the model sees the reminder on this turn, and every turn after it

Claude Code and Codex CLI both read the ``hookSpecificOutput.additionalContext``
shape on their ``UserPromptSubmit`` event, so one script serves both. The hook
writes nothing and runs no tools itself.
"""

from __future__ import annotations

import json
import sys

import _path_setup  # noqa: F401

from hooks_constants.style_reminder_prompt_constants import STYLE_REMINDER_PROMPT


def build_style_reminder() -> str:
    """Return the style reminder text emitted on every prompt."""
    return STYLE_REMINDER_PROMPT


def main() -> None:
    """Emit the style reminder as UserPromptSubmit additionalContext."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": build_style_reminder(),
        }
    }
    sys.stdout.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    main()
