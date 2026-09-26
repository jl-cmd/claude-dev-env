#!/usr/bin/env python3
"""Turn the step-notes gate on or off, or report its state.

The gate is on while STEP_NOTES_ON_FLAG_PATH exists and off by default. `on`
creates the flag file, `off` removes it, `flip` does whichever changes the
state, and `status` changes nothing. The flag applies to every session on
this machine.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

scripts_directory = str(Path(__file__).resolve().parent)
if scripts_directory not in sys.path:
    sys.path.insert(0, scripts_directory)

from step_notes_constants.toggle_step_notes_constants import (
    ALL_ACTIONS,
    FLIP_ACTION,
    OFF_ACTION,
    OFF_REPORT,
    ON_ACTION,
    ON_REPORT,
    STEP_NOTES_ON_FLAG_PATH,
)


def apply_action(action: str) -> bool:
    """Apply one action to the flag file and return whether step notes are on."""
    is_on = STEP_NOTES_ON_FLAG_PATH.exists()
    if action == FLIP_ACTION:
        action = OFF_ACTION if is_on else ON_ACTION
    if action == ON_ACTION:
        STEP_NOTES_ON_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        STEP_NOTES_ON_FLAG_PATH.touch()
        return True
    if action == OFF_ACTION:
        STEP_NOTES_ON_FLAG_PATH.unlink(missing_ok=True)
        return False
    return is_on


def main(all_arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default=FLIP_ACTION, choices=ALL_ACTIONS)
    parsed_arguments = parser.parse_args(all_arguments)
    print(ON_REPORT if apply_action(parsed_arguments.action) else OFF_REPORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
