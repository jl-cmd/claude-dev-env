from pathlib import Path

from hooks_constants import step_note_gate_constants as constants


def test_gate_uses_the_step_notes_flag_location() -> None:
    assert constants.STEP_NOTES_ON_FLAG_PATH == Path.home() / ".claude" / ".step-notes-on"


def test_gate_uses_transcript_roles_and_block_types() -> None:
    assert (constants.USER_ROLE, constants.ASSISTANT_ROLE) == ("user", "assistant")
    assert (constants.TEXT_BLOCK_TYPE, constants.TOOL_USE_BLOCK_TYPE) == (
        "text",
        "tool_use",
    )


def test_gate_exit_codes_and_message_match_the_hook_contract() -> None:
    assert (constants.ALLOW_EXIT_CODE, constants.BLOCK_EXIT_CODE) == (0, 2)
    assert "Status line missing." in constants.BLOCK_MESSAGE
    assert "/step-notes" in constants.BLOCK_MESSAGE
