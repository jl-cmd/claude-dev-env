"""Run a command and compare its stdout, parsed as JSON, with an expected JSON value.

Exit 0 on equality, 1 on any difference or non-JSON output, 3 when the command cannot start.
"""

from __future__ import annotations

import json
import subprocess
import sys

from config.json_stdout_equals_constants import (
    COMMAND_TIMEOUT_SECONDS,
    HARNESS_EXIT,
    MINIMUM_ARGUMENT_COUNT,
)


def main(all_arguments: list[str]) -> int:
    """Grade a command by the JSON its stdout carries.

    ::

        arguments: '{"lines": 3}'  python -m wordcount sample.txt --json
        stdout '{"lines": 3}'   ->   exit 0
        stdout '{"lines": 4}'   ->   exit 1
        stdout 'lines: 3'       ->   exit 1

    Args:
        all_arguments: The expected JSON text, then the command words to run.
            A command word of ``python`` runs this interpreter.

    Returns:
        0 when the command exits 0 and its stdout parses to the expected JSON,
        1 on any difference or on stdout that is not JSON, and the harness exit
        code when the arguments are too few or the command cannot start.
    """
    if len(all_arguments) < MINIMUM_ARGUMENT_COUNT:
        return HARNESS_EXIT
    expected = json.loads(all_arguments[0])
    all_command_parts = [sys.executable if each_part == "python" else each_part for each_part in all_arguments[1:]]
    try:
        completed = subprocess.run(
            all_command_parts,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return HARNESS_EXIT
    try:
        produced = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return 1
    return 0 if completed.returncode == 0 and produced == expected else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
