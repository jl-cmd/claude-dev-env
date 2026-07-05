#!/usr/bin/env python3
"""SessionStart hook — start a task-list maintenance loop for the session.

At session start this hook emits an ``additionalContext`` directive asking Claude
to keep the session's task list current on a 10-minute cadence, starting the loop
skill when one is not already running. The hook writes nothing and runs no tools
itself. Claude reads the directive and invokes the loop skill.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.task_list_loop_starter_constants import (  # noqa: E402
    TASK_LIST_LOOP_DIRECTIVE,
)


def build_session_directive() -> str:
    """Return the task-list loop directive emitted at session start."""
    return TASK_LIST_LOOP_DIRECTIVE


def main() -> None:
    """Emit the task-list loop directive as SessionStart additionalContext."""
    print(json.dumps({"additionalContext": build_session_directive()}))


if __name__ == "__main__":
    main()
