#!/usr/bin/env python3
import fnmatch
import json
import os
import sys

SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
    "package-lock.json",
    "yarn.lock",
    "Pipfile.lock",
    "poetry.lock",
    "pnpm-lock.yaml",
    "composer.lock",
]

WRITE_EDIT_TOOLS = {"Write", "Edit"}


def is_sensitive_file(file_path: str) -> str | None:
    filename = os.path.basename(file_path)
    for each_pattern in SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(filename, each_pattern):
            return each_pattern
    return None


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name not in WRITE_EDIT_TOOLS:
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    matched_pattern = is_sensitive_file(file_path)

    if matched_pattern is not None:
        deny_response = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"BLOCKED: Sensitive file '{os.path.basename(file_path)}' (pattern: '{matched_pattern}'). Edit manually outside Claude Code."
            }
        }
        print(json.dumps(deny_response))

    sys.exit(0)


if __name__ == "__main__":
    main()
