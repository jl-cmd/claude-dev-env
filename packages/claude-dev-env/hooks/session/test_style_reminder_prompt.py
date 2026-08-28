"""Tests for style_reminder_prompt — UserPromptSubmit hook that injects the style reminder."""

import json
from io import StringIO
from unittest.mock import patch

import style_reminder_prompt as reminder
from hooks_constants.style_reminder_prompt_constants import STYLE_REMINDER_PROMPT


def _run_main() -> str:
    """Return the stdout the hook's main() writes."""
    captured_stdout = StringIO()
    with patch("sys.stdout", captured_stdout):
        reminder.main()
    return captured_stdout.getvalue()


class TestStyleReminderPrompt:
    def test_main_emits_user_prompt_submit_hook_specific_output(self) -> None:
        emitted = json.loads(_run_main())
        assert emitted["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"

    def test_additional_context_matches_style_reminder_exactly(self) -> None:
        emitted = json.loads(_run_main())
        assert emitted["hookSpecificOutput"]["additionalContext"] == STYLE_REMINDER_PROMPT

    def test_build_style_reminder_returns_the_shared_constant(self) -> None:
        assert reminder.build_style_reminder() == STYLE_REMINDER_PROMPT
