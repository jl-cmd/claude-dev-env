#!/usr/bin/env python3
"""PreToolUse hook: block SendUserFile attaches that should open locally.

SendUserFile attaches a file to the session. While the user is at the terminal
(status "normal" or unset) an attach does not let them see the file — it must
open on screen in its own viewer via Show-Asset.ps1. The one attach allowed
through is an away-from-desk phone push (status "proactive").
"""

import json
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.send_user_file_open_locally_blocker_constants import (  # noqa: E402
    CORRECTIVE_MESSAGE,
    PROACTIVE_STATUS,
    TOOL_NAME,
)


def _should_block(status: str) -> bool:
    """Return whether a SendUserFile call with this status should be denied.

    Args:
        status: The ``status`` field from the SendUserFile input. A proactive
            phone push is allowed; every other value, including an empty one,
            is a desk-side attach the user cannot see and is denied.
    """
    return status != PROACTIVE_STATUS


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("tool_name", "") != TOOL_NAME:
        sys.exit(0)

    tool_input = hook_input.get("tool_input") or {}
    status = tool_input.get("status", "")
    if not _should_block(status):
        sys.exit(0)

    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": CORRECTIVE_MESSAGE,
        }
    }
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
