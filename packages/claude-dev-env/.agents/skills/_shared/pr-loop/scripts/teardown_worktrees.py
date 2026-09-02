"""Remove git worktrees and run temp directories for a bugteam run.

Usage:
  python scripts/teardown_worktrees.py --run-temp-dir <PATH> --all-pr-jsons <JSON>

The JSON array must contain objects with keys: number, owner, repo.
Tolerates already-removed worktrees and missing directories.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

_self_dir = Path(__file__).resolve().parent
if str(_self_dir) not in sys.path:
    sys.path.insert(0, str(_self_dir))

from _path_resolver import per_pr_workspace
from skills_pr_loop_constants.path_resolver_constants import ALL_PYTHON_ONEXC_VERSION


def _remove_readonly_attribute(
    removal_function: Callable[[str], None],
    target_path: str,
    *_exc_info: object,
) -> None:
    """Windows-safe handler: strip ReadOnly attribute and retry the syscall.

    Args:
        removal_function: The syscall that failed (os.unlink or os.rmdir).
        target_path: Path to the file or directory that triggered the error.
        *_exc_info: Exception information (collapses onerror/onexc signature difference).
    """
    try:
        os.chmod(target_path, stat.S_IWRITE)
        removal_function(target_path)
    except OSError:
        pass


def force_rmtree(target_path: str) -> None:
    """Remove a directory tree, handling Windows ReadOnly attribute.

    Args:
        target_path: Path to the directory tree to remove.
    """
    handler_kw: dict[str, object] = (
        {"onexc": _remove_readonly_attribute}
        if sys.version_info >= ALL_PYTHON_ONEXC_VERSION
        else {"onerror": _remove_readonly_attribute}
    )
    try:
        shutil.rmtree(target_path, **handler_kw)
    except OSError:
        pass


def remove_worktree(worktree_path: Path) -> bool:
    """Remove a single git worktree via `git worktree remove`.

    Args:
        worktree_path: Path to the worktree directory.

    Returns:
        True when the worktree was registered and removed, False when
        it was already absent or unregistered.
    """
    if not worktree_path.exists():
        return False
    completed_process = subprocess.run(
        ["git", "worktree", "remove", str(worktree_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed_process.returncode != 0:
        stderr_text = completed_process.stderr or ""
        if "not a working tree" in stderr_text.lower():
            force_rmtree(str(worktree_path))
            return False
        print(
            f"git worktree remove failed for {worktree_path}: {stderr_text}",
            file=sys.stderr,
        )
        return False
    return True


def teardown_run(
    *,
    run_temp_dir: Path,
    all_pr_entries: list[dict[str, object]],
) -> int:
    """Remove all worktrees and the run temp directory.

    Args:
        run_temp_dir: Path to the run's temp directory.
        all_pr_entries: List of dicts with number, owner, and repo keys.

    Returns:
        Count of worktrees successfully removed via git.
    """
    removed_count = 0
    for each_entry in all_pr_entries:
        pr_number = each_entry.get("number")
        owner = each_entry.get("owner", "")
        repo = each_entry.get("repo", "")
        if not isinstance(pr_number, int):
            continue
        workspace = per_pr_workspace(run_temp_dir, str(owner), str(repo), pr_number)
        if remove_worktree(workspace.worktree):
            removed_count += 1

    force_rmtree(str(run_temp_dir))
    return removed_count


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with run_temp_dir and all_pr_jsons.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-temp-dir", type=Path, required=True)
    parser.add_argument("--all-pr-jsons", required=True)
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point: remove worktrees and temp directory.

    Args:
        all_arguments: Command-line arguments.

    Returns:
        0 on success, 1 on JSON parse failure.
    """
    arguments = parse_arguments(all_arguments)
    run_temp_dir = getattr(arguments, "run_temp_dir")
    try:
        all_pr_entries = json.loads(getattr(arguments, "all_pr_jsons"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON for --all-pr-jsons: {exc}", file=sys.stderr)
        return 1
    if not isinstance(all_pr_entries, list):
        print("--all-pr-jsons must be a JSON array", file=sys.stderr)
        return 1

    removed_count = teardown_run(
        run_temp_dir=run_temp_dir,
        all_pr_entries=all_pr_entries,
    )
    print(f"Removed {removed_count} worktree(s), cleaned {run_temp_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
