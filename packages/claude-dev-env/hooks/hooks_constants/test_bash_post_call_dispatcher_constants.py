"""Behavioral tests for the Bash PostToolUse dispatcher's hosted-hook roster."""

from hooks_constants.bash_post_call_dispatcher_constants import (
    ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES,
)
from hooks_constants.bash_pre_tool_use_dispatcher_constants import BASH_TOOL_NAME


def test_roster_names_the_test_failure_recorder_hook() -> None:
    all_script_paths = [
        each_entry.script_relative_path for each_entry in ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES
    ]
    assert "observability/test_failure_recorder.py" in all_script_paths


def test_every_roster_entry_applies_to_bash() -> None:
    assert all(
        BASH_TOOL_NAME in each_entry.applicable_tool_names
        for each_entry in ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES
    )
