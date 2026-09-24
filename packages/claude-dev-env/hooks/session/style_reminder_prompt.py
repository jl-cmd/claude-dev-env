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
their ``UserPromptSubmit`` event. The Claude hook includes the skill reminder
when its flag is present. The unflagged Codex hook prints style alone.
"""

from __future__ import annotations

import json
import sys

import _path_setup  # noqa: F401

from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
from hooks_constants.style_reminder_prompt_constants import STYLE_REMINDER_PROMPT
from skill_loaded_reminder import reminder_for


def _additional_context_for_prompt() -> str:
    if "--include-skill-reminder" not in sys.argv[1:]:
        return STYLE_REMINDER_PROMPT
    hook_input = read_hook_input_dictionary_from_stdin()
    if hook_input is None:
        return STYLE_REMINDER_PROMPT
    skill_reminder = reminder_for(hook_input)
    if skill_reminder is None:
        return STYLE_REMINDER_PROMPT
    return STYLE_REMINDER_PROMPT + "\n" + skill_reminder


def main() -> None:
    """Print ordered UserPromptSubmit additionalContext."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": _additional_context_for_prompt(),
        }
    }
    sys.stdout.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    main()
