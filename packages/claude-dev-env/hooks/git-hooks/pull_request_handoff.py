from __future__ import annotations

import subprocess
from pathlib import Path

from git_hooks_constants import (
    GH_EXECUTABLE_NAME,
    GH_PR_VIEW_ARGUMENTS,
    GH_PR_VIEW_TIMEOUT_SECONDS,
)


def get_pull_request_url(repo_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            [GH_EXECUTABLE_NAME, *GH_PR_VIEW_ARGUMENTS],
            cwd=repo_dir,
            check=False,
            capture_output=True,
            text=True,
            timeout=GH_PR_VIEW_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def build_pull_request_reminder(url: str) -> str:
    return (
        f"Reminder: use {url}; read the PR body and complete diff, never choose the title "
        "from the branch name, commit message, labels, current title, or shallow summary; "
        "use gh pr edit to set the title/body, read it back, and report the link, commit, "
        "result, and checks."
    )
