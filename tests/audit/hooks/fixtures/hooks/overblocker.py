"""Calibration known-bad: denies every call, the valid near-neighbor included."""

import json
import sys


def main() -> None:
    sys.stdin.read()
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "everything is prohibited",
                }
            }
        )
    )


if __name__ == "__main__":
    main()
