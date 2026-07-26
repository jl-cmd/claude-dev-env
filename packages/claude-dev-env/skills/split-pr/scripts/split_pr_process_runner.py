"""One subprocess layer for every git and gh call the split-pr scripts make.

::

    run_checked_git(["push", branch], repo_root, "push failed for %s: %s", (branch,))
    # ok:   returns the completed process
    # flag: RuntimeError("push failed for <branch>: <stderr>")

Each runner decodes as UTF-8 with ``errors="replace"`` so a non-ASCII byte in
git or gh output reports the failure instead of raising a decode error. The
checked runners take the error template and the context values that precede the
captured detail, which keeps one raise site behind every failing command.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from split_pr_scripts_constants.config.common_constants import (
    GH_COMMAND,
    GH_REPO_FLAG,
)
from split_pr_scripts_constants.config.execute_constants import (
    GIT_COMMAND,
    MARKDOWN_BODY_SUFFIX,
)

ErrorContext = tuple[object, ...]


def read_failure_detail(completed: subprocess.CompletedProcess[str]) -> str:
    """Return the text a command left behind, preferring stderr.

    Args:
        completed: A finished process with captured text output.

    Returns:
        Trimmed stderr, falling back to trimmed stdout, else an empty string.
    """
    return (completed.stderr or completed.stdout or "").strip()


def run_command(
    all_command: list[str],
    working_directory: str | None,
) -> subprocess.CompletedProcess[str]:
    """Run one command to completion and capture its text output.

    Args:
        all_command: Executable and arguments to run.
        working_directory: Directory to run in, or None for the current one.

    Returns:
        The completed process, carrying return code, stdout, and stderr.
    """
    return subprocess.run(
        all_command,
        cwd=working_directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def raise_on_failure(
    completed: subprocess.CompletedProcess[str],
    error_template: str,
    all_error_context: ErrorContext,
) -> None:
    """Raise the template's error when the command reported failure.

    Args:
        completed: A finished process to inspect.
        error_template: Percent-format template whose last placeholder takes
            the captured failure detail.
        all_error_context: Values filling the template's earlier placeholders.

    Raises:
        RuntimeError: When the return code is non-zero.
    """
    if completed.returncode == 0:
        return
    raise RuntimeError(
        error_template % (*all_error_context, read_failure_detail(completed))
    )


def run_git(
    all_git_arguments: list[str],
    repo_root: Path,
) -> subprocess.CompletedProcess[str]:
    """Run one git subcommand in repo_root without raising on failure.

    Args:
        all_git_arguments: Arguments that follow the ``git`` executable.
        repo_root: Directory the command runs in.

    Returns:
        The completed process for the caller to inspect.
    """
    return run_command([GIT_COMMAND, *all_git_arguments], str(repo_root))


def run_checked_git(
    all_git_arguments: list[str],
    repo_root: Path,
    error_template: str,
    all_error_context: ErrorContext,
) -> subprocess.CompletedProcess[str]:
    """Run one git subcommand and raise the template's error on failure.

    Args:
        all_git_arguments: Arguments that follow the ``git`` executable.
        repo_root: Directory the command runs in.
        error_template: Percent-format template for the failure message.
        all_error_context: Values filling the template's earlier placeholders.

    Returns:
        The completed process when git succeeded.

    Raises:
        RuntimeError: When git reported a non-zero return code.
    """
    completed = run_git(all_git_arguments, repo_root)
    raise_on_failure(completed, error_template, all_error_context)
    return completed


def build_gh_command(all_gh_arguments: list[str], repo: str | None) -> list[str]:
    """Return the full gh command, appending ``--repo`` when one is named.

    ::

        build_gh_command([GH_PR, GH_CLOSE, "7"], "owner/name")
        # ok: ["gh", "pr", "close", "7", "--repo", "owner/name"]

    Args:
        all_gh_arguments: Arguments that follow the ``gh`` executable.
        repo: ``owner/name`` slug, or None to let gh infer the repository.

    Returns:
        The command list to run.
    """
    all_command = [GH_COMMAND, *all_gh_arguments]
    if repo:
        all_command.extend([GH_REPO_FLAG, repo])
    return all_command


def run_gh(
    all_gh_arguments: list[str],
    repo: str | None,
    working_directory: str | None,
    error_template: str,
    all_error_context: ErrorContext,
) -> str:
    """Run one gh command and return its stdout, raising on failure.

    Args:
        all_gh_arguments: Arguments that follow the ``gh`` executable.
        repo: ``owner/name`` slug, or None to let gh infer the repository.
        working_directory: Directory to run in, or None for the current one.
        error_template: Percent-format template for the failure message.
        all_error_context: Values filling the template's earlier placeholders.

    Returns:
        Trimmed stdout from the successful command.

    Raises:
        RuntimeError: When gh reported a non-zero return code.
    """
    completed = run_command(
        build_gh_command(all_gh_arguments, repo),
        working_directory,
    )
    raise_on_failure(completed, error_template, all_error_context)
    return (completed.stdout or "").strip()


def write_markdown_body_file(body_text: str) -> str:
    """Write body_text to a temporary markdown file and return its path.

    The file outlives this call so ``gh --body-file`` can read it; the caller
    unlinks it once gh has run.

    Args:
        body_text: Markdown to place on disk.

    Returns:
        Absolute path to the written file.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=MARKDOWN_BODY_SUFFIX,
        delete=False,
    ) as body_file:
        body_file.write(body_text)
        return body_file.name
