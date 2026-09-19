"""Calibration control: deny a Bash command that names the forbidden operation."""

import json
import sys


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    command = payload.get("tool_input", {}).get("command", "")
    if payload.get("tool_name") != "Bash" or "forbidden-op --force" not in command:
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "forbidden-op --force is prohibited",
                }
            }
        )
    )


if __name__ == "__main__":
    main()
