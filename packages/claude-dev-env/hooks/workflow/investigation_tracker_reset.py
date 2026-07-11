#!/usr/bin/env python3
"""PostToolUse hook — resets the serial investigation tracker when delegation occurs.

Clears the investigation timestamp tracker when the lead session delegates work
via Agent, Task, or TeamCreate tools. This allows the lead to resume limited
diagnostic calls after properly delegating.

Companion: blocking/serial-investigation-blocker.py (PreToolUse on Read|Bash|Grep)
"""

import json
import os
import sys

TRACKER_STATE_PATH = os.path.join(
    os.path.expanduser("~"), ".claude", "runtime", "investigation-tracker.json"
)

DELEGATION_TOOLS = frozenset({"Agent", "Task", "TeamCreate"})


def clear_investigation_tracker() -> None:
    try:
        os.remove(TRACKER_STATE_PATH)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in DELEGATION_TOOLS:
        sys.exit(0)

    clear_investigation_tracker()
    sys.exit(0)


if __name__ == "__main__":
    main()
