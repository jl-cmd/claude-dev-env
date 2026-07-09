"""Tests for the Bash and PowerShell dispatcher hosted-hook roster.

The roster order and per-hook applicable-tool sets fix the firing sequence and
tool coverage the dispatcher must reproduce, so these tests pin both against the
registration order the standalone chain used.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (  # noqa: E402
    ALL_BASH_AND_POWERSHELL_TOOL_NAMES,
    ALL_BASH_HOSTED_HOOK_ENTRIES,
    BASH_TOOL_NAME,
    POWERSHELL_TOOL_NAME,
)

_EXPECTED_BASH_ORDER = (
    "blocking/es_exe_path_rewriter.py",
    "blocking/destructive_command_blocker.py",
    "blocking/gh_body_arg_blocker.py",
    "blocking/nas_ssh_binary_enforcer.py",
    "blocking/volatile_path_in_post_blocker.py",
    "blocking/conventional_pr_title_gate.py",
    "blocking/reviewer_spawn_gate.py",
    "blocking/block_main_commit.py",
    "blocking/precommit_code_rules_gate.py",
    "blocking/session_edit_stage_gate.py",
    "blocking/pr_description_enforcer.py",
    "blocking/test_preflight_check.py",
    "blocking/convergence_gate_blocker.py",
    "blocking/windows_rmtree_blocker.py",
    "blocking/gh_pr_author_enforcer.py",
    "blocking/verified_commit_gate.py",
    "blocking/verdict_directory_write_blocker.py",
)

_POWERSHELL_APPLICABLE = (
    "blocking/verified_commit_gate.py",
    "blocking/verdict_directory_write_blocker.py",
)


def test_roster_lists_all_bash_hooks_in_registration_order() -> None:
    """The roster reproduces the standalone Bash chain order exactly."""
    actual_order = tuple(
        each_entry.script_relative_path for each_entry in ALL_BASH_HOSTED_HOOK_ENTRIES
    )
    assert actual_order == _EXPECTED_BASH_ORDER


def test_every_hook_applies_to_the_bash_tool() -> None:
    """Every hosted hook runs on a Bash tool call."""
    for each_entry in ALL_BASH_HOSTED_HOOK_ENTRIES:
        assert BASH_TOOL_NAME in each_entry.applicable_tool_names


def test_only_the_verified_commit_pair_applies_to_powershell() -> None:
    """Only the verified-commit gate and verdict-directory blocker run on PowerShell."""
    powershell_hooks = tuple(
        each_entry.script_relative_path
        for each_entry in ALL_BASH_HOSTED_HOOK_ENTRIES
        if POWERSHELL_TOOL_NAME in each_entry.applicable_tool_names
    )
    assert powershell_hooks == _POWERSHELL_APPLICABLE


def test_powershell_hooks_carry_the_shared_tool_set() -> None:
    """The PowerShell-applicable hooks name both Bash and PowerShell."""
    for each_entry in ALL_BASH_HOSTED_HOOK_ENTRIES:
        if each_entry.script_relative_path in _POWERSHELL_APPLICABLE:
            assert each_entry.applicable_tool_names == ALL_BASH_AND_POWERSHELL_TOOL_NAMES


def test_every_roster_path_points_at_an_existing_hook() -> None:
    """Each roster path names a hook script present on disk, catching a typo."""
    hooks_root = Path(__file__).resolve().parent.parent
    for each_entry in ALL_BASH_HOSTED_HOOK_ENTRIES:
        assert (hooks_root / each_entry.script_relative_path).is_file()
