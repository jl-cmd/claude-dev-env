"""Tests for the Bash and PowerShell dispatcher hosted-hook roster."""

from pathlib import Path
from runpy import run_path

ALL_CONSTANT_BINDINGS = run_path(
    str(Path(__file__).with_name("bash_pre_tool_use_dispatcher_constants.py"))
)
ALL_BASH_HOSTED_HOOK_ENTRIES = ALL_CONSTANT_BINDINGS["ALL_BASH_HOSTED_HOOK_ENTRIES"]


def test_roster_has_no_blocking_hooks() -> None:
    assert ALL_BASH_HOSTED_HOOK_ENTRIES == ()
