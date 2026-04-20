#!/usr/bin/env python3
"""Git pre-commit hook: run the CODE_RULES gate over staged changes.

Installed to the user's shared git-hooks directory via the claude-dev-env
installer; git invokes this file as `pre-commit` (the installer strips the
`_` and `.py` suffix when copying into the live hooks path).

Exit codes:
  0 - staged changes pass the gate (or the gate is not installed locally).
  1 - staged changes introduce one or more blocking violations.
  2 - unexpected invocation failure (e.g., subprocess could not launch).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from config import (
    GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE,
    GATE_SCRIPT_NOT_FOUND_MESSAGE,
    INVOKE_GATE_FAILURE_MESSAGE,
    STAGED_SCOPE_ARGUMENT,
)
from gate_utils import is_safe_regular_file, resolve_gate_script_path


def invoke_gate(gate_script_path: Path) -> int:
    staged_scope_argument = STAGED_SCOPE_ARGUMENT
    invoke_gate_failure_message = INVOKE_GATE_FAILURE_MESSAGE
    gate_infrastructure_failure_exit_code = GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    try:
        resolved_gate_path = gate_script_path.resolve(strict=True)
        completion = subprocess.run(
            [sys.executable, str(resolved_gate_path), staged_scope_argument],
            check=False,
        )
    except OSError as launch_error:
        print(
            invoke_gate_failure_message.format(error=launch_error),
            file=sys.stderr,
        )
        return gate_infrastructure_failure_exit_code
    return completion.returncode


def main() -> int:
    gate_script_not_found_message = GATE_SCRIPT_NOT_FOUND_MESSAGE
    gate_script_path, exact_allowed_path = resolve_gate_script_path()
    if not is_safe_regular_file(gate_script_path, exact_allowed_path):
        print(
            gate_script_not_found_message.format(path=gate_script_path),
            file=sys.stderr,
        )
        return 0
    return invoke_gate(gate_script_path)


if __name__ == "__main__":
    sys.exit(main())
