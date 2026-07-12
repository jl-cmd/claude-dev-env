"""Skill-path entry for bugteam code_rules_gate.

Delegates to the package shared home:
``_shared/pr-loop/scripts/code_rules_gate.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_shared_pr_loop_scripts_directory = (
    Path(__file__).resolve().parents[3] / "_shared" / "pr-loop" / "scripts"
)
if str(_shared_pr_loop_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_shared_pr_loop_scripts_directory))

from code_rules_gate import (  # noqa: E402
    main,
)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
