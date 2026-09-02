"""Library helper: resolve a directory's Git repository root.

``pii_prevention_blocker.py`` and ``pii_payload_scan.py`` import
``resolve_repository_root`` to find the repository a staged-commit scan
targets, and ``session_edit_stage_gate.py`` imports it to find the
repository a commit's unstaged-edit check targets. This module carries no
hook entry point of its own; the native ``git-hooks/pre_commit.py`` runs
the real commit-time CODE_RULES enforcement.
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
