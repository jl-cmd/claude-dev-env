#!/usr/bin/env python3
"""Advisory hook: warn when Django migrations contain unsafe operations."""

import json
import re
import sys

MIGRATION_PATH_PATTERN = re.compile(r"[/\\]migrations[/\\]\d{4}_\w+\.py$")
UNSAFE_OPERATIONS = ["RemoveField", "RenameField", "DeleteModel", "RenameModel"]


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not MIGRATION_PATH_PATTERN.search(file_path):
        sys.exit(0)

    content = tool_input.get("content", "") or tool_input.get("new_string", "")
    found_unsafe = [op for op in UNSAFE_OPERATIONS if op in content]

    if found_unsafe:
        operations = ", ".join(found_unsafe)
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": (
                            f"MIGRATION SAFETY: Contains {operations}. "
                            "Post-launch, model changes MUST be backwards-compatible. "
                            "Verify this won't break running instances during deployment."
                        ),
                    }
                }
            )
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
