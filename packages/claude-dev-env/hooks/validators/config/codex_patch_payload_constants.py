"""Payload keys the validators read from a Codex apply_patch call.

A Codex patch arrives as one command string naming several paths, so the gate
reads the command rather than a single file path, and takes the working
directory the patch's relative paths resolve against from the payload.
"""

from __future__ import annotations

__all__ = [
    "CODEX_APPLY_PATCH_TOOL_NAME",
    "CODEX_PATCH_COMMAND_KEY",
    "PAYLOAD_WORKING_DIRECTORY_KEY",
]

CODEX_APPLY_PATCH_TOOL_NAME = "apply_patch"
CODEX_PATCH_COMMAND_KEY = "command"
PAYLOAD_WORKING_DIRECTORY_KEY = "cwd"
