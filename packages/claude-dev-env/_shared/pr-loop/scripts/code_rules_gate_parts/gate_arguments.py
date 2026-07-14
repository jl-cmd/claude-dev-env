"""Parse the command-line arguments for the code-rules gate."""

import argparse
from pathlib import Path


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the repo-root, base-ref, and staged-mode arguments to *parser*."""
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: cwd).",
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Merge-base ref for git diff (default: origin/main).",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        default=False,
        help="Scope to staged changes only (git diff --cached).",
    )


def _add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the only-under filter and the explicit-paths arguments to *parser*."""
    parser.add_argument(
        "--only-under",
        action="append",
        default=[],
        dest="only_under",
        metavar="PREFIX",
        help="Keep only files whose repo-relative POSIX path starts with or "
        "equals PREFIX (repeatable).",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional explicit files; if set, git diff is not used.",
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    """Return the argument parser with every gate option registered."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the code-rules validators on files in the working tree. Default "
            "file set: git diff since the merge-base joined with untracked files."
        ),
    )
    _add_source_arguments(parser)
    _add_filter_arguments(parser)
    return parser


def parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
    """Parse the command-line arguments for the code-rules gate.

    Args:
        all_arguments: Command-line argument list forwarded to argparse.

    Returns:
        The parsed namespace with ``repo_root``, ``base``, ``staged``,
        ``only_under``, and ``paths`` attributes.
    """
    return _build_argument_parser().parse_args(all_arguments)
