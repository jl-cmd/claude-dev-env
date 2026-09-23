"""Tests for skill_loaded_reminder. Checks every fresh context gets poteto-mode, and loaded ones hear nothing."""

import json
import sys
from io import BytesIO, StringIO, TextIOWrapper
from pathlib import Path
from unittest.mock import patch

_SESSION_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _SESSION_DIR.parent
for each_sys_path_entry in (str(_SESSION_DIR), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

import skill_loaded_reminder as reminder
from hooks_constants.skill_loaded_reminder_constants import (
    COMPACTION_REMINDER,
    NOT_LOADED_REMINDER,
)

SKILL_CALL_LINE = json.dumps(
    {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "Skill",
                    "input": {"skill": "pstack:poteto-mode"},
                }
            ],
        },
    }
)
TYPED_COMMAND_LINE = json.dumps(
    {
        "type": "user",
        "message": {
            "role": "user",
            "content": "<command-name>/pstack:poteto-mode</command-name>",
        },
    }
)
COMPACT_BOUNDARY_LINE = json.dumps({"type": "system", "subtype": "compact_boundary"})
READ_CALL_LINE = json.dumps(
    {
        "type": "assistant",
        "message": {
            "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}]
        },
    }
)
TOOL_RESULT_QUOTING_THE_SKILL_LINE = json.dumps(
    {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "content": 'SKILL = "pstack:poteto-mode" and <command-name>/pstack:poteto-mode</command-name>',
                }
            ]
        },
    }
)


def _run_main(hook_payload: object) -> str:
    """Return the text main() prints for the given hook payload."""
    stdin_text = hook_payload if isinstance(hook_payload, str) else json.dumps(hook_payload)
    captured_stdout = StringIO()
    fake_stdin = TextIOWrapper(BytesIO(stdin_text.encode("utf-8")), encoding="utf-8")
    with patch("sys.stdin", fake_stdin), patch("sys.stdout", captured_stdout):
        reminder.main()
    return captured_stdout.getvalue()


def _agent_call(tool_input: dict[str, object], tool_name: str = "Agent") -> dict[str, object]:
    return {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input}


def _user_turn(transcript_path: Path) -> dict[str, object]:
    return {"hook_event_name": "UserPromptSubmit", "transcript_path": str(transcript_path)}


def _write_transcript(tmp_path: Path, all_lines: list[str]) -> Path:
    transcript_path = tmp_path / "session.jsonl"
    transcript_path.write_text("\n".join(all_lines) + "\n", encoding="utf-8")
    return transcript_path


class TestSubagentSpawn:
    def test_a_plain_subagent_prompt_opens_with_the_poteto_mode_invocation(self) -> None:
        emitted = json.loads(
            _run_main(
                _agent_call(
                    {
                        "description": "Find callers",
                        "subagent_type": "Explore",
                        "prompt": "List every caller of main.",
                    }
                )
            )
        )
        hook_output = emitted["hookSpecificOutput"]
        rewritten_input = hook_output["updatedInput"]
        assert hook_output["permissionDecision"] == "allow"
        assert rewritten_input["prompt"].startswith(
            "Before any other work, invoke the pstack:poteto-mode skill with the Skill tool."
        )
        assert rewritten_input["prompt"].endswith("\n\nList every caller of main.")
        assert rewritten_input["subagent_type"] == "Explore"
        assert rewritten_input["description"] == "Find callers"

    def test_the_legacy_task_tool_name_is_rewritten_too(self) -> None:
        emitted = json.loads(_run_main(_agent_call({"prompt": "Go."}, tool_name="Task")))
        assert "pstack:poteto-mode" in emitted["hookSpecificOutput"]["updatedInput"]["prompt"]

    def test_a_prompt_that_already_names_the_skill_is_left_alone(self) -> None:
        assert _run_main(_agent_call({"prompt": "Invoke pstack:poteto-mode first. Then go."})) == ""

    def test_a_poteto_agent_is_left_alone_because_it_loads_the_skill_itself(self) -> None:
        assert (
            _run_main(_agent_call({"subagent_type": "pstack:poteto-agent", "prompt": "Go."})) == ""
        )

    def test_another_tool_is_left_alone(self) -> None:
        assert _run_main(_agent_call({"prompt": "Go."}, tool_name="Bash")) == ""


class TestSubagentInputWithPotetoMode:
    def test_every_other_input_field_is_kept(self) -> None:
        rewritten_input = reminder.subagent_input_with_poteto_mode(
            {"prompt": "Go.", "model": "sonnet", "run_in_background": True}
        )
        assert rewritten_input is not None
        assert rewritten_input["model"] == "sonnet"
        assert rewritten_input["run_in_background"] is True

    def test_an_input_with_no_prompt_is_left_alone(self) -> None:
        assert reminder.subagent_input_with_poteto_mode({"description": "Go"}) is None


class TestIsPotetoModeLoaded:
    def test_a_skill_call_loads_it(self) -> None:
        assert reminder.is_poteto_mode_loaded([READ_CALL_LINE, SKILL_CALL_LINE, READ_CALL_LINE])

    def test_a_typed_slash_command_loads_it(self) -> None:
        assert reminder.is_poteto_mode_loaded([TYPED_COMMAND_LINE, READ_CALL_LINE])

    def test_a_compaction_after_the_skill_call_drops_it(self) -> None:
        assert not reminder.is_poteto_mode_loaded(
            [SKILL_CALL_LINE, COMPACT_BOUNDARY_LINE, READ_CALL_LINE]
        )

    def test_a_skill_call_after_the_compaction_loads_it_again(self) -> None:
        assert reminder.is_poteto_mode_loaded(
            [SKILL_CALL_LINE, COMPACT_BOUNDARY_LINE, SKILL_CALL_LINE]
        )

    def test_a_plain_user_prompt_does_not_load_it(self) -> None:
        plain_prompt_line = json.dumps(
            {"type": "user", "message": {"content": "Read pstack:poteto-mode docs."}}
        )
        assert not reminder.is_poteto_mode_loaded([plain_prompt_line])

    def test_a_tool_result_that_quotes_the_skill_name_does_not_load_it(self) -> None:
        assert not reminder.is_poteto_mode_loaded([TOOL_RESULT_QUOTING_THE_SKILL_LINE])


class TestReminderFor:
    def test_a_user_turn_in_a_session_that_never_loaded_the_skill_gets_the_reminder(
        self, tmp_path: Path
    ) -> None:
        transcript_path = _write_transcript(tmp_path, [READ_CALL_LINE])
        emitted = json.loads(_run_main(_user_turn(transcript_path)))
        hook_output = emitted["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "UserPromptSubmit"
        assert hook_output["additionalContext"] == NOT_LOADED_REMINDER
        assert "pstack:poteto-mode" in NOT_LOADED_REMINDER

    def test_a_user_turn_in_a_session_that_loaded_the_skill_prints_nothing(
        self, tmp_path: Path
    ) -> None:
        transcript_path = _write_transcript(tmp_path, [SKILL_CALL_LINE, READ_CALL_LINE])
        assert _run_main(_user_turn(transcript_path)) == ""

    def test_a_user_turn_with_no_transcript_yet_gets_the_reminder(self, tmp_path: Path) -> None:
        assert (
            reminder.reminder_for(_user_turn(tmp_path / "not-written-yet.jsonl"))
            == NOT_LOADED_REMINDER
        )

    def test_session_start_after_compaction_tells_the_session_to_invoke_it_again(self) -> None:
        emitted = json.loads(_run_main({"hook_event_name": "SessionStart", "source": "compact"}))
        hook_output = emitted["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "SessionStart"
        assert hook_output["additionalContext"] == COMPACTION_REMINDER
        assert "pstack:poteto-mode" in COMPACTION_REMINDER

    def test_a_resumed_session_keeps_its_context_and_prints_nothing(self) -> None:
        assert _run_main({"hook_event_name": "SessionStart", "source": "resume"}) == ""

    def test_a_payload_that_is_not_json_prints_nothing(self) -> None:
        assert _run_main("not json") == ""
