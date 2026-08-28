"""Tests for style_reminder_prompt. Checks the hook adds the style reminder."""

import json
from io import StringIO
from unittest.mock import patch

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
