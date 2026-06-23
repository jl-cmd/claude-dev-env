"""Tests for the PreToolUse dispatcher hosted-hook roster."""

import pathlib
import sys

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.pre_tool_use_dispatcher_constants import (
    ALL_HOSTED_HOOK_ENTRIES,
    ALL_WRITE_AND_EDIT_TOOL_NAMES,
    EDIT_TOOL_NAME,
    WRITE_TOOL_NAME,
)


def _entry_for(script_relative_path: str):
    matching_entries = [
        each_entry
        for each_entry in ALL_HOSTED_HOOK_ENTRIES
        if each_entry.script_relative_path == script_relative_path
    ]
    return matching_entries[0] if matching_entries else None


def test_roster_includes_duplicate_rmtree_helper_blocker_script_path() -> None:
    all_registered_script_paths = [
        each_entry.script_relative_path for each_entry in ALL_HOSTED_HOOK_ENTRIES
    ]
    assert "blocking/duplicate_rmtree_helper_blocker.py" in all_registered_script_paths, (
        "duplicate_rmtree_helper_blocker must be hosted by the dispatcher so a local "
        "re-definition of the Windows-safe rmtree helper trio is blocked at Write time"
    )


def test_duplicate_rmtree_helper_blocker_applies_to_write_and_edit() -> None:
    entry = _entry_for("blocking/duplicate_rmtree_helper_blocker.py")
    assert entry is not None
    assert WRITE_TOOL_NAME in entry.applicable_tool_names
    assert EDIT_TOOL_NAME in entry.applicable_tool_names


def test_duplicate_rmtree_helper_blocker_is_blocking() -> None:
    entry = _entry_for("blocking/duplicate_rmtree_helper_blocker.py")
    assert entry is not None
    assert entry.is_blocking is True


def test_duplicate_rmtree_helper_blocker_runs_via_runpy() -> None:
    entry = _entry_for("blocking/duplicate_rmtree_helper_blocker.py")
    assert entry is not None
    assert entry.native_module_name is None


def test_windows_rmtree_blocker_still_registered() -> None:
    entry = _entry_for("blocking/windows_rmtree_blocker.py")
    assert entry is not None
    assert entry.applicable_tool_names == ALL_WRITE_AND_EDIT_TOOL_NAMES
