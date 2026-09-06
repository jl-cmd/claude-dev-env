"""Library helper that resolves a directory to its Git repository root.

``pii_payload_scan.py`` imports ``resolve_repository_root`` for staged scans.
This module has no hook entry point. Native ``git-hooks/pre_commit.py`` shows
the local verification advisory and does not enforce CODE_RULES.
"""

import subprocess
import sys
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.precommit_code_rules_gate_constants import (  # noqa: E402
    ALL_GIT_REPOSITORY_ROOT_COMMAND,
    GIT_COMMAND_TIMEOUT_SECONDS,
)


def resolve_repository_root(working_directory: str | None) -> Path | None:
    """Resolve the Git repository root for a directory.

    Args:
        working_directory: Directory inside the repository.

    Returns:
        Repository root. Returns None when Git cannot resolve the directory.
    """
    try:
        completed_process = subprocess.run(
            list(ALL_GIT_REPOSITORY_ROOT_COMMAND),
            check=False,
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=working_directory,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if completed_process.returncode != 0:
        return None
    top_level_text = completed_process.stdout.strip()
    if not top_level_text:
        return None
    return Path(top_level_text)
