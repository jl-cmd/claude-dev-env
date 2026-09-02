#!/usr/bin/env python3
"""
PostToolUse hook that validates hook commands in settings.json use cross-platform format.
Blocks if hooks use simple 'python3 ~/.claude/...' instead of the exec(open(...)) pattern.
"""

import json
import re
import sys
from pathlib import Path

try:
    _hooks_dir = str(Path(__file__).resolve().parent.parent)
    if _hooks_dir not in sys.path:
        sys.path.insert(0, _hooks_dir)

    from hooks_constants.hook_block_logger import log_hook_block
    from hooks_constants.hook_format_validator_constants import (
        MULTI_EDIT_NEW_STRING_JOIN_SEPARATOR,
    )
    from hooks_constants.multi_edit_reconstruction import edits_for_tool
except ImportError as import_error:
    raise ImportError(
        "hook_format_validator: cannot import its sibling modules; "
        "ensure the hooks directory is importable."
    ) from import_error

SIMPLE_PATTERN = re.compile(
    r'python3?\s+~/\.claude/hooks/'
)


def _resolve_content(tool_name: str, all_tool_input: dict) -> str:
    """Return the text a Write, Edit, or MultiEdit payload introduces."""
    if tool_name == "MultiEdit":
        all_new_strings = [
            each_edit.get("new_string", "")
            for each_edit in edits_for_tool("MultiEdit", all_tool_input)
            if isinstance(each_edit, dict) and isinstance(each_edit.get("new_string"), str)
        ]
        return MULTI_EDIT_NEW_STRING_JOIN_SEPARATOR.join(all_new_strings)
    content = all_tool_input.get("content", "")
    if not content:
        content = all_tool_input.get("new_string", "")
    return content


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path.endswith("settings.json"):
        sys.exit(0)

    if "/.claude/" not in file_path and "\\.claude\\" not in file_path:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    content = _resolve_content(tool_name, tool_input)

    if tool_name == "Write" and content:
        try:
            with open(file_path, "r", encoding="utf-8") as existing_file:
                existing_content = existing_file.read()
            if existing_content:
                sys.exit(0)
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            pass

    if not content:
        sys.exit(0)

    if SIMPLE_PATTERN.search(content):
        message = "BLOCKED: Hook uses python3 ~/.claude/hooks/... format which breaks cross-platform. Use this pattern: node -e \"process.argv.splice(1,0,'_');require(require('os').homedir()+'/.claude/hooks/run-hook-wrapper.js')\" \"subfolder/your-hook.py\""
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message
            }
        }
        log_hook_block(
            calling_hook_name="hook_format_validator.py",
            hook_event="PreToolUse",
            block_reason=message,
            tool_name=tool_name,
            offending_input_preview=file_path,
        )
        print(json.dumps(result))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
