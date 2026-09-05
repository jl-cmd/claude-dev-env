"""Pin the PR done reminder's command shape and checklist wording."""

from __future__ import annotations

from hooks_constants import pr_done_reminder_constants as constants


def test_gh_probe_asks_for_every_field_the_checklist_reads() -> None:
    assert constants.ALL_GH_PR_VIEW_ARGUMENTS[:3] == ("gh", "pr", "view")
    all_requested_fields = constants.ALL_GH_PR_VIEW_ARGUMENTS[-1].split(",")
    for each_field in ("number", "url", "isDraft", "mergeable", "statusCheckRollup", "labels"):
        assert each_field in all_requested_fields


def test_git_global_options_that_take_a_value_are_named() -> None:
    assert constants.ALL_GIT_OPTIONS_WITH_VALUE == frozenset({"-C", "-c"})


def test_powershell_wrappers_and_their_command_flags_are_named() -> None:
    assert "pwsh" in constants.ALL_POWERSHELL_PROGRAM_NAMES
    assert "powershell" in constants.ALL_POWERSHELL_PROGRAM_NAMES
    assert "-command" in constants.ALL_POWERSHELL_COMMAND_FLAGS
    assert "-c" in constants.ALL_POWERSHELL_COMMAND_FLAGS


def test_checklist_lines_join_on_a_single_newline() -> None:
    assert constants.REMINDER_LINE_SEPARATOR == "\n"


def test_every_mergeable_value_has_a_hint() -> None:
    assert set(constants.ALL_REMINDER_HINTS_BY_MERGEABLE) == {
        constants.MERGEABLE_CLEAN_VALUE,
        constants.MERGEABLE_CONFLICTING_VALUE,
        constants.MERGEABLE_UNKNOWN_VALUE,
    }


def test_header_says_it_never_blocks() -> None:
    assert "never a block" in constants.REMINDER_HEADER
    assert "never a block" in constants.NO_PULL_REQUEST_REMINDER
