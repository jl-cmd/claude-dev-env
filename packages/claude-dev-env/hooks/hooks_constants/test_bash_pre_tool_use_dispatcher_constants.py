"""Tests for the Bash and PowerShell dispatcher hosted-hook roster."""

from pathlib import Path
from runpy import run_path

ALL_CONSTANT_BINDINGS = run_path(
    str(Path(__file__).with_name("bash_pre_tool_use_dispatcher_constants.py"))
)
ALL_BASH_HOSTED_HOOK_ENTRIES = ALL_CONSTANT_BINDINGS["ALL_BASH_HOSTED_HOOK_ENTRIES"]
ALL_BASH_ONLY_TOOL_NAMES = ALL_CONSTANT_BINDINGS["ALL_BASH_ONLY_TOOL_NAMES"]
BashHostedHookEntry = ALL_CONSTANT_BINDINGS["BashHostedHookEntry"]


def test_roster_hosts_only_the_msys_rewriter_and_no_blocking_hook() -> None:
    assert ALL_BASH_HOSTED_HOOK_ENTRIES == (
        BashHostedHookEntry(
            script_relative_path="blocking/msys_rev_path_rewriter.py",
            applicable_tool_names=ALL_BASH_ONLY_TOOL_NAMES,
        ),
    )
