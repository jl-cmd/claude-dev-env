from pathlib import Path

from step_notes_constants.config import constants


def test_flag_path_matches_the_step_notes_location() -> None:
    assert constants.STEP_NOTES_ON_FLAG_PATH == Path.home() / ".claude" / ".step-notes-on"


def test_actions_match_the_toggle_command() -> None:
    assert (
        constants.ON_ACTION,
        constants.OFF_ACTION,
        constants.STATUS_ACTION,
        constants.FLIP_ACTION,
    ) == ("on", "off", "status", "flip")
    assert constants.ALL_ACTIONS == ("on", "off", "status", "flip")


def test_reports_describe_the_flag_state() -> None:
    assert constants.ON_REPORT == (
        "Step notes are on. Each tool call needs a short status line before it."
    )
    assert constants.OFF_REPORT == "Step notes are off. Tool calls run without a status line."
