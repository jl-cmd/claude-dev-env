#!/usr/bin/env python3
"""Shared ``gh pr comment --body-file`` helpers for split-pr scripts."""

from __future__ import annotations

import subprocess
import tempfile

from split_pr_scripts_constants.config.execute_constants import (
    GH_BODY_FILE,
    GH_COMMAND,
    GH_COMMENT,
    GH_PR,
    GH_REPO_FLAG,
    MARKDOWN_BODY_SUFFIX,
)


def write_markdown_body_file(comment_body: str) -> str:
    """Write comment markdown to a temp file and return its path.

    Args:
        comment_body: Full markdown body for ``gh pr comment``.

    Returns:
        Absolute path string for ``--body-file``.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=MARKDOWN_BODY_SUFFIX,
        delete=False,
    ) as body_file:
        body_file.write(comment_body)
        return body_file.name


def run_gh_pr_comment(
    pr_number: int,
    body_path: str,
    repo: str | None,
    working_directory: str | None,
    error_template: str,
) -> None:
    """Post a PR comment from a body file.

    Args:
        pr_number: Target pull request number.
        body_path: Path passed to ``--body-file``.
        repo: Optional ``owner/name`` for ``gh --repo``.
        working_directory: Cwd for the ``gh`` process.
        error_template: ``%``-format string taking ``(pr_number, detail)``.

    Raises:
        RuntimeError: When ``gh pr comment`` exits non-zero.
    """
    all_command = [
        GH_COMMAND,
        GH_PR,
        GH_COMMENT,
        str(pr_number),
        GH_BODY_FILE,
        body_path,
    ]
    if repo:
        all_command.extend([GH_REPO_FLAG, repo])
    completed = subprocess.run(
        all_command,
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(error_template % (pr_number, detail))
