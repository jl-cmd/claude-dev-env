#!/usr/bin/env python3
"""
TDD enforcement hook.

Prompts confirmation when writing/editing production code files.
Skips: Test files, config files, documentation.
"""
import json
import sys
from pathlib import Path

PRODUCTION_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx'}
SKIP_PATTERNS = {
    'test_', '_test.', '.test.', 'tests/', '__tests__/',
    'conftest', 'fixture', 'mock', 'stub'
}
SKIP_EXTENSIONS = {'.md', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.txt'}


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    path = Path(file_path)
    ext = path.suffix.lower()

    # Skip config/docs
    if ext in SKIP_EXTENSIONS:
        sys.exit(0)

    # Skip non-production code files
    if ext not in PRODUCTION_EXTENSIONS:
        sys.exit(0)

    # Skip test files
    name_lower = path.name.lower()
    path_str = str(path).lower()
    if any(pattern in name_lower or pattern in path_str for pattern in SKIP_PATTERNS):
        sys.exit(0)

    # Block production code - require confirmation
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": "[TDD] Writing production code. Confirm you have a failing test first."
        }
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
