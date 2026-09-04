"""Shared names for mutation and shell tools."""

from __future__ import annotations

BASH_TOOL_NAME: str = "Bash"
POWERSHELL_TOOL_NAME: str = "PowerShell"
WRITE_TOOL_NAME: str = "Write"
EDIT_TOOL_NAME: str = "Edit"
MULTI_EDIT_TOOL_NAME: str = "MultiEdit"
APPLY_PATCH_TOOL_NAME: str = "apply_patch"

ALL_BASH_AND_POWERSHELL_TOOL_NAMES: frozenset[str] = frozenset(
    {BASH_TOOL_NAME, POWERSHELL_TOOL_NAME}
)
ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES: frozenset[str] = frozenset(
    {WRITE_TOOL_NAME, EDIT_TOOL_NAME, MULTI_EDIT_TOOL_NAME}
)
ALL_WRITE_EDIT_MULTI_EDIT_APPLY_PATCH_TOOL_NAMES: frozenset[str] = frozenset(
    ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES | {APPLY_PATCH_TOOL_NAME}
)
