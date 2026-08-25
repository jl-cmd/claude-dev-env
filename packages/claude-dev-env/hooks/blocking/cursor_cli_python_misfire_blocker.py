#!/usr/bin/env python3
"""PreToolUse hook: deny Cursor launches that mistreat a Python gate script.

Agents sometimes run ``cursor code_rules_gate.py --base origin/main`` (or the
same shape through ``Cursor.exe`` / ``cursor.cmd``) when the intent is either
to execute the gate or to open a file. Cursor's main process then hits
``onUnknownOption`` for the gate flags, ``console.warn`` writes to a closed
pipe, and Windows shows an EPIPE error dialog — while still opening the
``.py`` path in the editor.

::

    cursor code_rules_gate.py --base origin/main     flag
    Cursor.exe gate.py --staged                      flag
    cursor.cmd path/to/x.py --repo-root .            flag
    cursor code_rules_gate.py                        ok: editor open, no gate flags
    cursor -g file.py:10                             ok: editor goto, no gate flags
    cursor README.md                                 ok: open without gate flags
    python code_rules_gate.py --base origin/main     ok: real gate run
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.cursor_cli_python_misfire_blocker_constants import (  # noqa: E402
    ALL_SUPPORTED_TOOL_NAMES,
    CALLING_HOOK_NAME,
    COMMAND_KEY,
    CORRECTIVE_MESSAGE,
    CURSOR_LAUNCH_PATTERN,
    DENY_DECISION,
    GATE_FLAG_PATTERN,
    GATE_SCRIPT_PATTERN,
    HOOK_EVENT_NAME,
    HOOK_EVENT_NAME_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    PERMISSION_DECISION_KEY,
    PERMISSION_DECISION_REASON_KEY,
    PYTHON_PATH_PATTERN,
    TOOL_INPUT_KEY,
    TOOL_NAME_KEY,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def is_cursor_python_gate_misfire(command: str) -> bool:
    """Return True when *command* launches Cursor against a gate-shaped Python run.

    Args:
        command: Raw Bash or PowerShell command string from the tool input.

    Returns:
        True when Cursor is the launch target, a gate CLI flag is present, and
        the operands name the gate script or another ``.py`` path.
    """
    if not command or not CURSOR_LAUNCH_PATTERN.search(command):
        return False
    if not GATE_FLAG_PATTERN.search(command):
        return False
    return bool(GATE_SCRIPT_PATTERN.search(command) or PYTHON_PATH_PATTERN.search(command))


def main() -> None:
    hook_input = read_hook_input_dictionary_from_stdin()
    if hook_input is None:
        sys.exit(0)

    tool_name = hook_input.get(TOOL_NAME_KEY, "")
    if tool_name not in ALL_SUPPORTED_TOOL_NAMES:
        sys.exit(0)

    tool_input = hook_input.get(TOOL_INPUT_KEY) or {}
    if not isinstance(tool_input, dict):
        sys.exit(0)
    command = tool_input.get(COMMAND_KEY, "")
    if not isinstance(command, str) or not is_cursor_python_gate_misfire(command):
        sys.exit(0)

    deny_payload = {
        HOOK_SPECIFIC_OUTPUT_KEY: {
            HOOK_EVENT_NAME_KEY: HOOK_EVENT_NAME,
            PERMISSION_DECISION_KEY: DENY_DECISION,
            PERMISSION_DECISION_REASON_KEY: CORRECTIVE_MESSAGE,
        }
    }
    log_hook_block(
        calling_hook_name=CALLING_HOOK_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=CORRECTIVE_MESSAGE,
        tool_name=str(tool_name),
    )
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
