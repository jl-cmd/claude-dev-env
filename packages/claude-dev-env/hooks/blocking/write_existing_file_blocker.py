#!/usr/bin/env python3
"""PreToolUse:Write hook — blocks Write tool when the target file already exists.

Agents should use Edit for modifying existing files. Write is only for new file creation.
Exemptions: Jupyter notebooks (.ipynb) and files in ~/.claude/hooks/ (standalone scripts).
"""

import json
import os
import sys

JUPYTER_EXTENSION = ".ipynb"
HOOKS_DIRECTORY = os.path.normpath(os.path.expanduser("~/.claude/hooks"))


def is_jupyter_notebook(file_path: str) -> bool:
    return file_path.lower().endswith(JUPYTER_EXTENSION)


def is_inside_hooks_directory(file_path: str) -> bool:
    normalized_path = os.path.normpath(file_path)
    return normalized_path.startswith(HOOKS_DIRECTORY)


def main() -> None:
    try:
        input_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_payload.get("tool_name", "")
    tool_input = input_payload.get("tool_input", {})

    if tool_name != "Write":
        sys.exit(0)

    target_file_path = tool_input.get("file_path", "")

    if not target_file_path:
        sys.exit(0)

    if is_jupyter_notebook(target_file_path):
        sys.exit(0)

    if is_inside_hooks_directory(target_file_path):
        sys.exit(0)

    if not os.path.exists(target_file_path):
        sys.exit(0)

    denial = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"BLOCKED: Write on existing file {target_file_path}. Use Edit tool instead.",
        }
    }
    print(json.dumps(denial))
    sys.exit(0)


if __name__ == "__main__":
    main()
