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
from hooks_constants.skill_loaded_reminder_constants import NOT_LOADED_REMINDER
from hooks_constants.style_reminder_prompt_constants import STYLE_REMINDER_PROMPT


def _run_main(all_arguments: list[str], hook_input: str) -> str:
    """Return the text main() prints."""
    captured_stdout = StringIO()
    with (
        patch("sys.argv", ["style_reminder_prompt.py", *all_arguments]),
        patch("sys.stdin", StringIO(hook_input)),
        patch("sys.stdout", captured_stdout),
    ):
        reminder.main()
    return captured_stdout.getvalue()


class TestStyleReminderPrompt:
    def test_main_emits_user_prompt_submit_hook_specific_output(self) -> None:
        emitted = json.loads(_run_main([], ""))
        hook_output = emitted["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "UserPromptSubmit"
        assert hook_output["additionalContext"] == STYLE_REMINDER_PROMPT

    def test_unflagged_invocation_keeps_style_only_with_hook_input(self) -> None:
        emitted = json.loads(_run_main([], json.dumps({"hook_event_name": "UserPromptSubmit"})))
        assert emitted["hookSpecificOutput"]["additionalContext"] == STYLE_REMINDER_PROMPT

    def test_flagged_invocation_combines_style_and_missing_skill_reminder(self) -> None:
        emitted = json.loads(
            _run_main(
                ["--include-skill-reminder"],
                json.dumps({"hook_event_name": "UserPromptSubmit"}),
            )
        )
        assert emitted["hookSpecificOutput"]["additionalContext"] == (
            STYLE_REMINDER_PROMPT + "\n" + NOT_LOADED_REMINDER
        )

    def test_flagged_invocation_keeps_style_only_after_skill_load(self, tmp_path: Path) -> None:
        transcript_path = tmp_path / "session.jsonl"
        transcript_path.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Skill",
                                "input": {"skill": "pstack:poteto-mode"},
                            }
                        ]
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        emitted = json.loads(
            _run_main(
                ["--include-skill-reminder"],
                json.dumps(
                    {"hook_event_name": "UserPromptSubmit", "transcript_path": str(transcript_path)}
                ),
            )
        )
        assert emitted["hookSpecificOutput"]["additionalContext"] == STYLE_REMINDER_PROMPT

    def test_flagged_invocation_without_hook_input_keeps_style_only(self) -> None:
        emitted = json.loads(_run_main(["--include-skill-reminder"], ""))
        assert emitted["hookSpecificOutput"]["additionalContext"] == STYLE_REMINDER_PROMPT
