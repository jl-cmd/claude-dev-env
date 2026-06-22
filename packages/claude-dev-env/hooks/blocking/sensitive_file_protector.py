#!/usr/bin/env python3
import fnmatch
import json
import os
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402

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
        deny_reason = f"BLOCKED: Sensitive file '{os.path.basename(file_path)}' (pattern: '{matched_pattern}'). Edit manually outside Claude Code."
        deny_response = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        }
        log_hook_block(
            calling_hook_name="sensitive_file_protector.py",
            hook_event="PreToolUse",
            block_reason=deny_reason,
            offending_input_preview=file_path,
        )
        print(json.dumps(deny_response))

    sys.exit(0)


if __name__ == "__main__":
    main()
