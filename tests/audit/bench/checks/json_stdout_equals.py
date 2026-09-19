"""Run a command and compare its stdout, parsed as JSON, with an expected JSON value.

Exit 0 on equality, 1 on any difference or non-JSON output, 3 when the command cannot start.
"""

from __future__ import annotations

import json
import subprocess
import sys

HARNESS_EXIT = 3


def main(all_arguments: list[str]) -> int:
    if len(all_arguments) < 2:
        return HARNESS_EXIT
    expected = json.loads(all_arguments[0])
    all_command_parts = [sys.executable if each_part == "python" else each_part for each_part in all_arguments[1:]]
    try:
        completed = subprocess.run(all_command_parts, capture_output=True, text=True, timeout=60, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return HARNESS_EXIT
    try:
        produced = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return 1
    return 0 if completed.returncode == 0 and produced == expected else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
