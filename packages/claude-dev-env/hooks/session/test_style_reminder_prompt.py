"""Tests for style_reminder_prompt. Checks the hook adds the style reminder."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

_SESSION_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _SESSION_DIR.parent
for each_sys_path_entry in (str(_SESSION_DIR), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

import style_reminder_prompt as reminder
from hooks_constants.style_reminder_prompt_constants import STYLE_REMINDER_PROMPT


def _run_main() -> str:
    """Return the text main() prints."""
    captured_stdout = StringIO()
    with patch("sys.stdout", captured_stdout):
        reminder.main()
    return captured_stdout.getvalue()


class TestStyleReminderPrompt:
    def test_main_emits_user_prompt_submit_hook_specific_output(self) -> None:
        emitted = json.loads(_run_main())
        hook_output = emitted["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "UserPromptSubmit"
        assert hook_output["additionalContext"] == STYLE_REMINDER_PROMPT
