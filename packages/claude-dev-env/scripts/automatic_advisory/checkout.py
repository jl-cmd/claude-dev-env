from __future__ import annotations

import subprocess
from pathlib import Path

from .config.constants import (
    ALL_GIT_HEAD_ARGUMENTS,
    ALL_GIT_STATUS_ARGUMENTS,
    GIT_BASE_REF_TEMPLATE,
    GIT_EXECUTABLE,
)
from .model import AdvisoryRegistration, LocalCheckout
from .window_flags import hidden_window_creation_flags


def read_local_checkout(checkout_path: Path) -> LocalCheckout:
    """Read the current commit and clean status for one checkout.

    Args:
        checkout_path: Git working tree to inspect.

    Returns:
        Commit and clean status, with no commit when Git cannot inspect it.
    """
    try:
        head_process = _run_git_command(ALL_GIT_HEAD_ARGUMENTS, checkout_path)
        status_process = _run_git_command(ALL_GIT_STATUS_ARGUMENTS, checkout_path)
    except OSError:
        return LocalCheckout(None, False)
    head_sha = head_process.stdout.strip() if head_process.returncode == 0 else None
    return LocalCheckout(
        head_sha,
        status_process.returncode == 0 and not status_process.stdout,
    )


def _run_git_command(
    all_arguments: tuple[str, ...], checkout_path: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (GIT_EXECUTABLE, *all_arguments),
        cwd=checkout_path,
        capture_output=True,
        check=False,
        text=True,
        creationflags=hidden_window_creation_flags(),
    )


def dedicated_base_ref(registration: AdvisoryRegistration) -> str:
    return GIT_BASE_REF_TEMPLATE.format(pull_request=registration.pull_request_number)
