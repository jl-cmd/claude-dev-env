#!/usr/bin/env python3
"""Advisory hook: warn when Django migrations contain unsafe operations."""

import json
import re
import sys
from pathlib import Path

try:
    _hooks_dir = str(Path(__file__).resolve().parent.parent)
    if _hooks_dir not in sys.path:
        sys.path.insert(0, _hooks_dir)

    from hooks_constants.migration_safety_advisor_constants import (
        MULTI_EDIT_NEW_STRING_JOIN_SEPARATOR,
        MULTI_EDIT_TOOL_NAME,
    )
    from hooks_constants.multi_edit_reconstruction import edits_for_tool
except ImportError as import_error:
    raise ImportError(
        "migration_safety_advisor: cannot import its sibling modules; "
        "ensure the hooks directory is importable."
    ) from import_error

MIGRATION_PATH_PATTERN = re.compile(r"[/\\]migrations[/\\]\d{4}_\w+\.py$")
UNSAFE_OPERATIONS = ["RemoveField", "RenameField", "DeleteModel", "RenameModel"]


def _resolve_content(tool_name: str, tool_input: dict) -> str:
    """Return the text a Write, Edit, or MultiEdit payload introduces."""
    if tool_name == MULTI_EDIT_TOOL_NAME:
        all_new_strings = [
            each_edit.get("new_string", "")
            for each_edit in edits_for_tool(MULTI_EDIT_TOOL_NAME, tool_input)
            if isinstance(each_edit, dict) and isinstance(each_edit.get("new_string"), str)
        ]
        return MULTI_EDIT_NEW_STRING_JOIN_SEPARATOR.join(all_new_strings)
    return tool_input.get("content", "") or tool_input.get("new_string", "")


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not MIGRATION_PATH_PATTERN.search(file_path):
        sys.exit(0)

    content = _resolve_content(tool_name, tool_input)
    found_unsafe = [op for op in UNSAFE_OPERATIONS if op in content]

    if found_unsafe:
        operations = ", ".join(found_unsafe)
        advisory_message = (
            f"MIGRATION SAFETY: Contains {operations}. "
            "Post-launch, model changes MUST be backwards-compatible. "
            "Verify this won't break running instances during deployment."
        )
        advisory_payload = {
            "systemMessage": advisory_message,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": advisory_message,
                "additionalContext": advisory_message,
            },
        }
        print(json.dumps(advisory_payload))

    sys.exit(0)


if __name__ == "__main__":
    main()
