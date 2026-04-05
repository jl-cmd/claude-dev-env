#!/usr/bin/env python3
"""
PostToolUse hook that validates hook commands in settings.json use cross-platform format.
Blocks if hooks use simple 'python3 ~/.claude/...' instead of the exec(open(...)) pattern.
"""

import json
import re
import sys


SIMPLE_PATTERN = re.compile(
    r'python3?\s+~/\.claude/hooks/'
)


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
    content = tool_input.get("content", "")
    if not content:
        new_string = tool_input.get("new_string", "")
        content = new_string

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
        print(json.dumps(result))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
