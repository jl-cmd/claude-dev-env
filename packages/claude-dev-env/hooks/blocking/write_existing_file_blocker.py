#!/usr/bin/env python3
"""PreToolUse hook — blocks Write and apply_patch "Add File" onto an existing target.

Agents should use Edit for modifying existing files, and an apply_patch
"Update File" section rather than "Add File" for a path that already exists.
Exemptions: Jupyter notebooks (.ipynb) and files in ~/.claude/hooks/ (standalone scripts).

MultiEdit carries no create-or-clobber path this hook needs to guard: every
MultiEdit edit must match an ``old_string`` already present in the target file,
so a MultiEdit can never introduce content nobody read the way a blind Write or
an apply_patch "Add File" can. This hook allows MultiEdit unconditionally.
"""

import json
import os
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

try:
    from codex_apply_patch import (
        CODEX_ADD_OPERATION,
        CodexPatchError,
        codex_patch_operation_targets,
        payload_patch_command,
    )
    from hooks_constants.hook_block_logger import log_hook_block
    from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
    from hooks_constants.pre_tool_use_dispatcher_constants import APPLY_PATCH_TOOL_NAME
    from sensitive_file_protector import build_deny_response
except ImportError as import_error:
    raise ImportError(
        "write_existing_file_blocker: cannot import its sibling modules; "
        "ensure the hooks directory is importable."
    ) from import_error

JUPYTER_EXTENSION = ".ipynb"
HOOKS_DIRECTORY = os.path.normpath(os.path.expanduser("~/.claude/hooks"))


def is_jupyter_notebook(file_path: str) -> bool:
    return file_path.lower().endswith(JUPYTER_EXTENSION)


def is_inside_hooks_directory(file_path: str) -> bool:
    normalized_path = os.path.normpath(file_path)
    return normalized_path.startswith(HOOKS_DIRECTORY)


def _apply_patch_add_deny(payload: dict, tool_input: dict) -> tuple[str, str] | None:
    """Return (deny_reason, offending_path) for an apply_patch 'Add File' onto an existing path."""
    command, working_directory = payload_patch_command(payload, tool_input)
    if not command:
        return None
    try:
        all_operation_targets = codex_patch_operation_targets(command, working_directory)
    except CodexPatchError:
        return None
    for each_operation, each_target_path in all_operation_targets:
        if each_operation != CODEX_ADD_OPERATION:
            continue
        if os.path.exists(each_target_path):
            deny_reason = (
                f"BLOCKED: apply_patch 'Add File' on existing file {each_target_path}. "
                "Use an 'Update File' section instead."
            )
            return deny_reason, each_target_path
    return None


def _write_onto_existing_file_deny(tool_input: dict) -> tuple[str, str] | None:
    """Return (deny_reason, offending_path) for a Write onto an existing target."""
    target_file_path = tool_input.get("file_path", "")
    if not target_file_path:
        return None
    if is_jupyter_notebook(target_file_path):
        return None
    if is_inside_hooks_directory(target_file_path):
        return None
    if not os.path.exists(target_file_path):
        return None
    deny_reason = f"BLOCKED: Write on existing file {target_file_path}. Use Edit tool instead."
    return deny_reason, target_file_path


def _resolve_deny(tool_name: str, payload: dict, tool_input: dict) -> tuple[str, str] | None:
    """Return (deny_reason, offending_path) for the payload, or None to allow."""
    if tool_name == APPLY_PATCH_TOOL_NAME:
        return _apply_patch_add_deny(payload, tool_input)
    if tool_name != "Write":
        return None
    return _write_onto_existing_file_deny(tool_input)


def main() -> None:
    input_payload = read_hook_input_dictionary_from_stdin()
    if input_payload is None:
        sys.exit(0)

    raw_tool_name = input_payload.get("tool_name", "")
    raw_tool_input = input_payload.get("tool_input", {})
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}

    resolved_deny = _resolve_deny(tool_name, input_payload, tool_input)
    if resolved_deny is None:
        sys.exit(0)
    deny_reason, offending_path = resolved_deny

    log_hook_block(
        calling_hook_name="write_existing_file_blocker.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
        offending_input_preview=offending_path,
    )
    print(json.dumps(build_deny_response(deny_reason)))
    sys.exit(0)


if __name__ == "__main__":
    main()
