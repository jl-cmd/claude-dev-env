"""Behavioral tests for the Bash PostToolUse dispatcher's hosted-hook roster."""

from hooks_constants import bash_post_call_dispatcher_constants as constants
from hooks_constants.bash_post_call_dispatcher_constants import (
    ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES,
)
from hooks_constants.bash_pre_tool_use_dispatcher_constants import BASH_TOOL_NAME


def test_roster_runs_the_recorder_then_the_pr_done_reminder() -> None:
    all_script_paths = [
        each_entry.script_relative_path for each_entry in ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES
    ]
    assert all_script_paths == [
        "observability/test_failure_recorder.py",
        "advisory/pr_done_reminder.py",
    ]


def test_pr_done_reminder_also_serves_the_powershell_tool() -> None:
    reminder_entry = ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES[-1]
    assert reminder_entry.script_relative_path == "advisory/pr_done_reminder.py"
    assert "PowerShell" in reminder_entry.applicable_tool_names


def test_context_forwarding_keys_match_the_hook_output_contract() -> None:
    assert constants.POST_TOOL_USE_HOOK_EVENT_NAME == "PostToolUse"
    assert constants.HOOK_SPECIFIC_OUTPUT_KEY == "hookSpecificOutput"
    assert constants.ADDITIONAL_CONTEXT_KEY == "additionalContext"
    assert constants.ADDITIONAL_CONTEXT_JOIN_SEPARATOR == "\n\n"


def test_every_roster_entry_applies_to_bash() -> None:
    assert all(
        BASH_TOOL_NAME in each_entry.applicable_tool_names
        for each_entry in ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES
    )
