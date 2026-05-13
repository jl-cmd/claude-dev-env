"""Recursively remove a directory tree, stripping Windows ReadOnly attributes.

Required by ~/.claude/rules/windows-filesystem-safe.md so bugteam teardown does
not silently swallow Windows ReadOnly-attribute failures the way the unsafe
shutil ignore-errors flag does.

Usage:
    python windows_safe_rmtree.py <absolute-path>
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from collections.abc import Callable

from config.windows_safe_rmtree_constants import (
    EXIT_CODE_REMOVE_TREE_FAILURE,
    EXIT_CODE_USAGE_ERROR,
    EXPECTED_ARGUMENT_COUNT,
    ONEXC_PYTHON_MAJOR_VERSION,
    ONEXC_PYTHON_MINOR_VERSION,
)


def _strip_read_only_and_retry(
    removal_function: Callable[[str], None],
    target_path: str,
    *_exc_info: object,
) -> None:
    try:
        os.chmod(target_path, os.stat(target_path).st_mode | stat.S_IWRITE)
        removal_function(target_path)
    except OSError as residual_error:
        sys.stderr.write(
            f"windows_safe_rmtree: chmod-and-retry could not remove {target_path}: "
            f"{type(residual_error).__name__}: {residual_error}\n"
        )


def _select_handler_keyword() -> dict[str, Callable[..., None]]:
    onexc_required_version = (
        ONEXC_PYTHON_MAJOR_VERSION,
        ONEXC_PYTHON_MINOR_VERSION,
    )
    if sys.version_info >= onexc_required_version:
        return {"onexc": _strip_read_only_and_retry}
    return {"onerror": _strip_read_only_and_retry}


def remove_tree(target_path: str) -> int:
    """Recursively remove a directory tree, handling Windows ReadOnly attributes.

    Args:
        target_path: Absolute path to the directory tree to remove.

    Returns:
        Zero when the tree was removed (or never existed). Non-zero when
        the chmod-and-retry handler could not finish cleanup; callers must
        treat a non-zero return as "tree may still be present".
    """
    if not os.path.exists(target_path):
        return 0
    handler_keyword = _select_handler_keyword()
    try:
        shutil.rmtree(target_path, **handler_keyword)
    except OSError as residual_error:
        sys.stderr.write(
            f"windows_safe_rmtree: residual failure removing {target_path}: "
            f"{type(residual_error).__name__}: {residual_error}\n"
        )
        return EXIT_CODE_REMOVE_TREE_FAILURE
    return 0


def _print_usage_to_stderr() -> None:
    sys.stderr.write("usage: python windows_safe_rmtree.py <absolute-path>\n")


def main(all_arguments: list[str]) -> int:
    """Parse command-line arguments and invoke remove_tree.

    Args:
        all_arguments: Command-line arguments including script name
                       and the target directory path.

    Returns:
        Exit code 0 on success, EXIT_CODE_USAGE_ERROR on invalid usage,
        EXIT_CODE_REMOVE_TREE_FAILURE when remove_tree could not finish.
    """
    if len(all_arguments) != EXPECTED_ARGUMENT_COUNT:
        _print_usage_to_stderr()
        return EXIT_CODE_USAGE_ERROR
    return remove_tree(all_arguments[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
