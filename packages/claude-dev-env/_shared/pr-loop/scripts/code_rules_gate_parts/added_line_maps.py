"""Map each changed file to the line numbers the current diff added.

The gate scopes a violation by whether its span meets an added line, so it needs
the added-line set per file. This module resolves that set for an ordinary
change, a brand-new file (its whole line span), and a rename (only the lines new
relative to the source blob).
"""

import subprocess
import sys
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    EXPECTED_NON_RENAME_COLUMN_COUNT,
    EXPECTED_RENAME_COLUMN_COUNT,
    GIT_NAME_STATUS_RENAMED_PREFIX,
)
from terminology_sweep import repository_environment

from code_rules_gate_parts.git_file_sets import (
    _git_bytes_or_exit,
    _git_text_or_exit,
    resolve_merge_base,
)
from code_rules_gate_parts.violation_scoping import parse_added_line_numbers


def _run_git_text_capture(
    repository_root: Path, all_git_arguments: list[str]
) -> subprocess.CompletedProcess[str]:
    """Run a git command in text mode and return the completed process."""
    return subprocess.run(
        all_git_arguments,
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=repository_environment(),
    )


def is_file_new_at_base(repository_root: Path, merge_base: str, relative_path_posix: str) -> bool:
    """Check whether *relative_path_posix* did not exist at *merge_base*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to check existence.
        relative_path_posix: Repository-relative POSIX path to inspect.

    Returns:
        True when the blob is absent at the merge base (added on the HEAD side).
    """
    completed = _run_git_text_capture(
        repository_root,
        ["git", "cat-file", "-e", f"{merge_base}:{relative_path_posix}"],
    )
    return completed.returncode != 0


def added_lines_for_file(
    repository_root: Path, merge_base: str, relative_path_posix: str
) -> set[int]:
    """Return added line numbers for *relative_path_posix* since *merge_base*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to diff.
        relative_path_posix: Repository-relative POSIX path to inspect.

    Returns:
        The line numbers added on the HEAD side of the diff.

    Raises:
        SystemExit: When the diff command returns non-zero.
    """
    diff_text = _git_text_or_exit(
        repository_root,
        ["git", "diff", "--unified=0", f"{merge_base}..HEAD", "--", relative_path_posix],
        f"code_rules_gate: git diff --unified=0 failed for {relative_path_posix}",
    )
    if not diff_text.strip():
        return set()
    return parse_added_line_numbers(diff_text)


def whole_file_line_set(file_path: Path) -> set[int]:
    """Return the set of line numbers covering an entire file.

    Args:
        file_path: Path to the file whose line span is summarized.

    Returns:
        Every line number in *file_path*, or an empty set when it is unreadable
        or empty.
    """
    try:
        total_lines = len(file_path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError) as read_error:
        sys.stderr.write(f"code_rules_gate: skipping unreadable file {file_path}: {read_error}\n")
        return set()
    if total_lines <= 0:
        return set()
    return set(range(1, total_lines + 1))


def _rename_pairs_from_tokens(all_tokens: list[str]) -> dict[str, str]:
    """Walk null-separated name-status tokens into destination-to-source pairs.

    Args:
        all_tokens: The decoded name-status tokens, in stream order.

    Returns:
        A mapping from rename-destination path to rename-source path.
    """
    rename_source_by_destination: dict[str, str] = {}
    next_token_index = 0
    while next_token_index < len(all_tokens):
        status_code = all_tokens[next_token_index]
        if not status_code.startswith(GIT_NAME_STATUS_RENAMED_PREFIX):
            next_token_index += EXPECTED_NON_RENAME_COLUMN_COUNT
            continue
        if next_token_index + EXPECTED_RENAME_COLUMN_COUNT > len(all_tokens):
            break
        rename_slice = all_tokens[
            next_token_index + 1 : next_token_index + EXPECTED_RENAME_COLUMN_COUNT
        ]
        destination_path = rename_slice[1].replace("\\", "/")
        rename_source_by_destination[destination_path] = rename_slice[0].replace("\\", "/")
        next_token_index += EXPECTED_RENAME_COLUMN_COUNT
    return rename_source_by_destination


def renamed_file_source_map_since(repository_root: Path, merge_base: str) -> dict[str, str]:
    """Return a mapping from rename-destination path to rename-source path.

    ::

        ok: a path holding a tab byte round-trips through the -z stream unmangled

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to diff.

    Returns:
        A mapping from rename-destination POSIX path to rename-source path.

    Raises:
        SystemExit: When ``git diff --name-status`` returns non-zero.
    """
    raw_stdout = _git_bytes_or_exit(
        repository_root,
        ["git", "diff", "--name-status", "-M", "-z", f"{merge_base}..HEAD"],
        "code_rules_gate: git diff --name-status -M -z failed",
    )
    all_tokens = [
        each_token.decode("utf-8", errors="replace")
        for each_token in raw_stdout.split(b"\x00")
        if each_token
    ]
    return _rename_pairs_from_tokens(all_tokens)


def added_lines_for_renamed_file(
    repository_root: Path,
    merge_base: str,
    source_posix: str,
    destination_posix: str,
) -> set[int]:
    """Return added line numbers for a renamed file via blob comparison.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to compare blobs.
        source_posix: Rename-source POSIX path at the merge base.
        destination_posix: Rename-destination POSIX path at HEAD.

    Returns:
        The line numbers added on the HEAD side; empty on diff failure.
    """
    source_reference = f"{merge_base}:{source_posix}"
    destination_reference = f"HEAD:{destination_posix}"
    completed = _run_git_text_capture(
        repository_root,
        ["git", "diff", "--unified=0", source_reference, destination_reference],
    )
    if completed.returncode != 0:
        sys.stderr.write(f"code_rules_gate: rename diff failed: {completed.stderr.strip()}\n")
        return set()
    if not completed.stdout.strip():
        return set()
    return parse_added_line_numbers(completed.stdout)


def _resolved_under_root(each_path: Path, resolved_root: Path) -> Path | None:
    """Return *each_path* resolved when it sits under *resolved_root*, else None."""
    try:
        resolved = each_path.resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved


def _added_lines_for_one_path(
    resolved_root: Path,
    merge_base: str,
    all_rename_sources: dict[str, str],
    resolved: Path,
) -> set[int]:
    """Resolve added lines for one path, honoring renames and new files.

    Args:
        resolved_root: The resolved repository root.
        merge_base: The merge-base SHA against which to diff.
        all_rename_sources: Destination-to-source rename map for the range.
        resolved: The resolved absolute path to inspect.

    Returns:
        The added line numbers for the path.
    """
    relative_posix = str(resolved.relative_to(resolved_root)).replace("\\", "/")
    if relative_posix in all_rename_sources:
        return added_lines_for_renamed_file(
            resolved_root, merge_base, all_rename_sources[relative_posix], relative_posix
        )
    added_numbers = added_lines_for_file(resolved_root, merge_base, relative_posix)
    if (
        not added_numbers
        and resolved.is_file()
        and is_file_new_at_base(resolved_root, merge_base, relative_posix)
    ):
        return whole_file_line_set(resolved)
    return added_numbers


def added_lines_by_file(
    repository_root: Path,
    base_reference: str,
    all_file_paths: list[Path],
    resolved_merge_base: str | None = None,
) -> dict[Path, set[int]]:
    """Build a per-file map of added line numbers across the branch.

    Args:
        repository_root: Repository root for diff invocations.
        base_reference: The git reference to merge-base against.
        all_file_paths: File paths whose added lines are collected.
        resolved_merge_base: Pre-resolved merge-base SHA; when omitted, the
            merge base of HEAD and *base_reference* is resolved here.

    Returns:
        A mapping from resolved file path to its added line numbers, with
        renames resolved against the original source path.
    """
    merge_base = (
        resolved_merge_base
        if resolved_merge_base is not None
        else resolve_merge_base(repository_root, base_reference)
    )
    resolved_root = repository_root.resolve()
    all_rename_sources = renamed_file_source_map_since(resolved_root, merge_base)
    added_by_path: dict[Path, set[int]] = {}
    for each_path in all_file_paths:
        resolved = _resolved_under_root(each_path, resolved_root)
        if resolved is None:
            continue
        added_by_path[resolved] = _added_lines_for_one_path(
            resolved_root, merge_base, all_rename_sources, resolved
        )
    return added_by_path
