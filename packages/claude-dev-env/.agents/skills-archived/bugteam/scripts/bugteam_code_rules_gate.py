"""Skill-path entry for bugteam code_rules_gate.

Delegates to the package shared home:
``_shared/pr-loop/scripts/code_rules_gate.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).resolve()
_skills_home_directory = _here.parents[3]
_package_or_user_home = (
    _skills_home_directory.parent
    if _skills_home_directory.name == ".agents"
    else _skills_home_directory
)
_shared_under_package = _package_or_user_home / "_shared" / "pr-loop" / "scripts"
_shared_pr_loop_scripts_directory = (
    _shared_under_package
    if _shared_under_package.is_dir()
    else _package_or_user_home / ".claude" / "_shared" / "pr-loop" / "scripts"
)
if str(_shared_pr_loop_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_shared_pr_loop_scripts_directory))

from code_rules_gate import (  # noqa: E402
    main,
)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
