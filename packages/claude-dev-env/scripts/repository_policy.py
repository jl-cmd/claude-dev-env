#!/usr/bin/env python3
"""Public command for the committed-tree repository checker."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Never, TextIO

from policy_lint.config.constants import ALL_GIT_ROOT_ARGUMENTS, UTF8_ENCODING
from policy_lint.selection_git import GitSelectionError, git_bytes_for
from repository_checks.config.constants import (
    ALL_CHECK_IDS,
    REPOSITORY_ROOT_FLAG,
    USAGE_EXIT_CODE,
)
from repository_checks.reporting import render_report
from repository_checks.runner import run_repository_checks

__all__ = ["ALL_CHECK_IDS", "main"]


class _RepositoryPolicyUsageError(ValueError):
    """Raised when command arguments cannot form a repository scan."""


class _RepositoryPolicyArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        """Raise a usage error for the caller.

        Args:
            message: Parser error text.

        Raises:
            _RepositoryPolicyUsageError: Always.
        """
        raise _RepositoryPolicyUsageError(message)


def _discover_repository_root(starting_directory: Path) -> Path:
    """Find the Git root that contains the command's current directory.

    Args:
        starting_directory: Directory where the command started.

    Returns:
        The resolved Git repository root.

    Raises:
        _RepositoryPolicyUsageError: If the directory is not inside a Git repository.
    """
    try:
        root_bytes = git_bytes_for(starting_directory.resolve(), ALL_GIT_ROOT_ARGUMENTS)
    except (GitSelectionError, OSError) as error:
        raise _RepositoryPolicyUsageError(
            "Current directory is not inside a Git repository"
        ) from error
    root_text = root_bytes.decode(UTF8_ENCODING).strip()
    if not root_text:
        raise _RepositoryPolicyUsageError("Git returned an empty repository root")
    return Path(root_text).resolve()


def _build_parser() -> argparse.ArgumentParser:
    parser = _RepositoryPolicyArgumentParser(prog="repository_policy")
    parser.add_argument(
        REPOSITORY_ROOT_FLAG,
        dest="repository_root",
        default=None,
        help="Git repository root to scan.",
    )
    return parser


def main(
    all_arguments: Sequence[str],
    *,
    repository_root: Path,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Run committed-tree repository checks.

    Args:
        all_arguments: Command arguments.
        repository_root: Repository root used when the flag is omitted.
        stdout: Output stream.
        stderr: Error stream.

    Returns:
        Zero when the tree is clean, one for findings, two for usage errors,
        and three when a check fails closed.
    """
    try:
        namespace = _build_parser().parse_args(list(all_arguments))
    except _RepositoryPolicyUsageError as usage_error:
        stderr.write(f"{usage_error}\n")
        return USAGE_EXIT_CODE
    selected_root = repository_root
    if namespace.repository_root is not None:
        selected_root = Path(namespace.repository_root).resolve()
    report = run_repository_checks(selected_root)
    stdout.write(render_report(report))
    return report.exit_code


if __name__ == "__main__":
    try:
        shell_directory = Path.cwd()
        parsed_namespace = _build_parser().parse_args(sys.argv[1:])
        if parsed_namespace.repository_root is not None:
            shell_repository_root = Path(parsed_namespace.repository_root).resolve()
        else:
            shell_repository_root = _discover_repository_root(shell_directory)
    except _RepositoryPolicyUsageError as usage_error:
        sys.stderr.write(f"{usage_error}\n")
        raise SystemExit(USAGE_EXIT_CODE) from usage_error
    raise SystemExit(main(sys.argv[1:], repository_root=shell_repository_root))
