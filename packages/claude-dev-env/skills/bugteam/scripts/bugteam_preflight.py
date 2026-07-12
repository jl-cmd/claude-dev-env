"""Skill-path entry for bugteam preflight.

Delegates to the package shared home:
``_shared/pr-loop/scripts/preflight.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_shared_pr_loop_scripts_directory = (
    Path(__file__).resolve().parents[3] / "_shared" / "pr-loop" / "scripts"
)
if str(_shared_pr_loop_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_shared_pr_loop_scripts_directory))

from preflight import (  # noqa: E402
    EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV,  # noqa: F401
    has_pytest_configuration,  # noqa: F401
    main,
    verify_git_hooks_path,  # noqa: F401
)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
