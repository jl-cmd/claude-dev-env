"""Skill-path entry for bugteam fix_hookspath.

Delegates to the package shared home:
``_shared/pr-loop/scripts/fix_hookspath.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_shared_pr_loop_scripts_directory = (
    Path(__file__).resolve().parents[2] / "_shared" / "pr-loop" / "scripts"
)
if str(_shared_pr_loop_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_shared_pr_loop_scripts_directory))

from fix_hookspath import (  # noqa: E402
    find_repository_root,  # noqa: F401
    is_canonical_hooks_path,  # noqa: F401
    list_local_core_hooks_path_values,  # noqa: F401
    main,
    normalize_hooks_path,  # noqa: F401
    read_global_core_hooks_path,  # noqa: F401
    resolve_canonical_hooks_directory,  # noqa: F401
    set_global_core_hooks_path,  # noqa: F401
    unset_local_core_hooks_path,  # noqa: F401
)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], None))
