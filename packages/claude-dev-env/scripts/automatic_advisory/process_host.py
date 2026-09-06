from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

from pr_verification.config.constants import INCOMPLETE_EXIT_CODE

from .config.constants import WINDOWS_PROCESS_START_SIGNAL


def run_owned_child(all_arguments: Sequence[str]) -> int:
    """Wait for ownership, then run the advisory child.

    Args:
        all_arguments: Child executable and arguments.

    Returns:
        Child exit code or the incomplete exit code when ownership is absent.
    """
    if sys.stdin.read(1) != WINDOWS_PROCESS_START_SIGNAL:
        return INCOMPLETE_EXIT_CODE
    completed_process = subprocess.run(
        tuple(all_arguments),
        shell=False,
        check=False,
    )
    return completed_process.returncode


if __name__ == "__main__":
    raise SystemExit(run_owned_child(sys.argv[1:]))
