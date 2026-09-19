"""Calibration control: block the same prohibited command through exit code 2."""

import json
import sys


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    command = payload.get("tool_input", {}).get("command", "")
    if payload.get("tool_name") == "Bash" and "forbidden-op --force" in command:
        print("forbidden-op --force is prohibited", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
