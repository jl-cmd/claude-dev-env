#!/usr/bin/env python3
"""SessionStart hook — inject working-style guidance into the session.

At session start this hook emits an ``additionalContext`` block carrying a fixed
working-style prompt: keep a running ledger, write in plain English, narrate
before the first tool call, lead with the outcome, and stay at the asked scope.
The hook writes nothing and runs no tools itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.working_style_prompt_constants import (  # noqa: E402
    WORKING_STYLE_PROMPT,
)


def build_session_directive() -> str:
    """Return the working-style prompt emitted at session start."""
    return WORKING_STYLE_PROMPT


def main() -> None:
    """Emit the working-style prompt as SessionStart additionalContext."""
    print(json.dumps({"additionalContext": build_session_directive()}))


if __name__ == "__main__":
    main()
