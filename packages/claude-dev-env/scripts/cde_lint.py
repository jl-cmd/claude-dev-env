#!/usr/bin/env python3
"""Run the policy linter."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Never, TextIO

from policy_lint.config.constants import INVALID_INPUT_EXIT_CODE
from policy_lint.engine import lint
from policy_lint.model import LintReport, LintRequest, SelectionKind, TextDocument
from policy_lint.render import ReportFormat, render
from policy_lint.selection import SelectionRunFatal
from policy_lint.selection_git import GitSelectionError, git_bytes_for


class _LintUsageError(ValueError):
    """Raised when command arguments cannot form a source selection."""


class _LintArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        """Raise a usage error instead of printing and exiting.

        Args:
            message: Parser error text.

        Raises:
            _LintUsageError: Always.
        """
        raise _LintUsageError(message)


def _discover_repository_root(starting_directory: Path) -> Path:
    """Find the Git root that contains the command's current directory.

    Args:
        starting_directory: Directory where the command started.

    Returns:
        The resolved Git repository root.

    Raises:
        _LintUsageError: If the directory is not inside a Git repository.
    """
    try:
        root_bytes = git_bytes_for(
            starting_directory.resolve(), ("rev-parse", "--show-toplevel")
        )
    except (GitSelectionError, OSError) as error:
        raise _LintUsageError("Current directory is not inside a Git repository") from error
    root_text = root_bytes.decode("utf-8").strip()
    if not root_text:
        raise _LintUsageError("Git returned an empty repository root")
    return Path(root_text).resolve()


def _resolve_shell_file_arguments(
    all_arguments: Sequence[str], starting_directory: Path
) -> list[str]:
    all_resolved_arguments: list[str] = []
    is_reading_file_paths = False
    for each_argument in all_arguments:
        if each_argument in ("--files", "--text-as"):
            is_reading_file_paths = True
            all_resolved_arguments.append(each_argument)
            continue
        if each_argument.startswith("--"):
            is_reading_file_paths = False
            all_resolved_arguments.append(each_argument)
            continue
        if not is_reading_file_paths:
            all_resolved_arguments.append(each_argument)
            continue
        candidate_path = Path(each_argument)
        all_resolved_arguments.append(
            str(
                candidate_path
                if candidate_path.is_absolute()
                else starting_directory / candidate_path
            )
        )
    return all_resolved_arguments


def _add_file_sources(source_group: argparse._MutuallyExclusiveGroup) -> None:
    source_group.add_argument(
        "--files",
        nargs="+",
        dest="all_file_paths",
        metavar="PATH",
        default=None,
        help="Lint current worktree files.",
    )
    source_group.add_argument(
        "--staged",
        action="store_const",
        const=SelectionKind.STAGED,
        dest="selection_kind",
        help="Lint staged index content.",
    )


def _add_repository_sources(
    source_group: argparse._MutuallyExclusiveGroup,
) -> None:
    source_group.add_argument(
        "--base",
        dest="base_revision",
        metavar="REVISION",
        default=None,
        help="Lint changes from a base revision.",
    )
    source_group.add_argument(
        "--repository",
        action="store_const",
        const=SelectionKind.REPOSITORY,
        dest="selection_kind",
        help="Lint tracked worktree files.",
    )
    source_group.add_argument(
        "--text-as",
        dest="text_path",
        metavar="PATH",
        default=None,
        help="Lint one editor buffer from standard input.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = _LintArgumentParser(prog="cde lint")
    source_group = parser.add_mutually_exclusive_group(required=True)
    _add_file_sources(source_group)
    _add_repository_sources(source_group)
    parser.add_argument(
        "--format",
        dest="report_format",
        choices=tuple(each_format.value for each_format in ReportFormat),
        default=ReportFormat.TEXT.value,
        help="Report format.",
    )
    parser.set_defaults(selection_kind=None)
    return parser


def _request_from_namespace(
    namespace: argparse.Namespace,
    stdin: TextIO,
    repository_root: Path,
) -> LintRequest:
    if namespace.all_file_paths is not None:
        return LintRequest.files(
            repository_root,
            [Path(each_path) for each_path in namespace.all_file_paths],
        )
    if namespace.base_revision is not None:
        return LintRequest.base(repository_root, namespace.base_revision)
    if namespace.text_path is not None:
        return LintRequest(
            repository_root,
            TextDocument(Path(namespace.text_path), stdin.read()),
        )
    if namespace.selection_kind is SelectionKind.STAGED:
        return LintRequest.staged(repository_root)
    if namespace.selection_kind is SelectionKind.REPOSITORY:
        return LintRequest.repository(repository_root)
    raise _LintUsageError("A source selection is required")


def _parse_lint_invocation(
    all_arguments: Sequence[str],
    stdin: TextIO,
    repository_root: Path,
) -> tuple[LintRequest, ReportFormat]:
    namespace = _build_parser().parse_args(list(all_arguments))
    return (
        _request_from_namespace(namespace, stdin, repository_root),
        ReportFormat(namespace.report_format),
    )


def _run_linter(
    all_arguments: Sequence[str],
    stdin: TextIO,
    repository_root: Path,
    lint_runner: Callable[[LintRequest], LintReport],
) -> tuple[LintReport, ReportFormat]:
    request, report_format = _parse_lint_invocation(
        list(all_arguments),
        stdin,
        repository_root,
    )
    return lint_runner(request), report_format


def _write_invalid_input(error: Exception, stderr: TextIO) -> int:
    stderr.write(f"{error}\n")
    return INVALID_INPUT_EXIT_CODE


def _render_lint(
    all_arguments: Sequence[str],
    repository_root: Path,
    stdin: TextIO,
    stdout: TextIO,
    lint_runner: Callable[[LintRequest], LintReport],
) -> int:
    report, report_format = _run_linter(
        all_arguments, stdin, repository_root, lint_runner
    )
    stdout.write(render(report, report_format))
    return report.exit_code


def main(
    all_arguments: Sequence[str],
    repository_root: Path,
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    lint_runner: Callable[[LintRequest], LintReport] = lint,
) -> int:
    """Run the policy-lint command.

    Args:
        all_arguments: Command arguments.
        repository_root: Repository root.
        stdin: Input stream.
        stdout: Output stream.
        stderr: Error stream.
        lint_runner: Policy-lint engine.

    Returns:
        The process exit code.
    """
    try:
        return _render_lint(
            all_arguments, repository_root, stdin, stdout, lint_runner
        )
    except _LintUsageError as usage_error:
        return _write_invalid_input(usage_error, stderr)
    except SelectionRunFatal as selection_error:
        return _write_invalid_input(selection_error, stderr)


if __name__ == "__main__":
    try:
        shell_directory = Path.cwd()
        shell_repository_root = _discover_repository_root(shell_directory)
    except _LintUsageError as usage_error:
        sys.stderr.write(f"{usage_error}\n")
        raise SystemExit(INVALID_INPUT_EXIT_CODE) from usage_error
    all_shell_arguments = _resolve_shell_file_arguments(sys.argv[1:], shell_directory)
    raise SystemExit(main(all_shell_arguments, shell_repository_root))
