"""Resolve the file sets the gate reads from git.

Every helper shells out to git with a scrubbed environment and null-terminated
output, so a filename holding a tab or newline round-trips unmangled. The path
readers turn ``-z`` streams into absolute paths; the staged helpers report the
added state and line span of one file.
"""

import subprocess
import sys
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    ALL_GIT_DIFF_CACHED_NAME_ONLY_NULL_TERMINATED_COMMAND,
    ALL_GIT_DIFF_NAME_ONLY_NULL_TERMINATED_COMMAND_PREFIX,
    ALL_GIT_LS_FILES_UNTRACKED_NULL_TERMINATED_COMMAND,
    GATE_ERROR_EXIT_CODE,
    GIT_NAME_STATUS_ADDED_PREFIX,
)
from terminology_sweep import repository_environment

__all__ = [
    "repository_environment",
    "resolve_merge_base",
    "paths_from_git_staged",
    "paths_from_git_diff",
    "paths_from_git_untracked",
    "filter_paths_under_prefixes",
    "is_staged_file_newly_added",
    "staged_file_line_count",
    "staged_unified_diff_text",
]


def _git_text_or_exit(
    repository_root: Path, all_git_arguments: list[str], failure_prefix: str
) -> str:
    """Run a git command in text mode, returning stdout or exiting on failure.

    Args:
        repository_root: Repository root used as the working directory.
        all_git_arguments: The full git argv, including the ``git`` word.
        failure_prefix: The stderr message prefix written on a non-zero exit.

    Returns:
        The command's stdout.

    Raises:
        SystemExit: When the git command returns non-zero.
    """
    completed = subprocess.run(
        all_git_arguments,
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=repository_environment(),
    )
    if completed.returncode != 0:
        sys.stderr.write(f"{failure_prefix}:\n{completed.stderr}\n")
        raise SystemExit(GATE_ERROR_EXIT_CODE)
    return completed.stdout


def _git_bytes_or_exit(
    repository_root: Path, all_git_arguments: list[str], failure_prefix: str
) -> bytes:
    """Run a git command in binary mode, returning stdout or exiting on failure.

    Args:
        repository_root: Repository root used as the working directory.
        all_git_arguments: The full git argv, including the ``git`` word.
        failure_prefix: The stderr message prefix written on a non-zero exit.

    Returns:
        The command's stdout bytes.

    Raises:
        SystemExit: When the git command returns non-zero.
    """
    completed = subprocess.run(
        all_git_arguments,
        cwd=str(repository_root),
        capture_output=True,
        check=False,
        env=repository_environment(),
    )
    if completed.returncode != 0:
        stderr_text = completed.stderr.decode("utf-8", errors="replace")
        sys.stderr.write(f"{failure_prefix}:\n{stderr_text}\n")
        raise SystemExit(GATE_ERROR_EXIT_CODE)
    return completed.stdout


def _null_separated_paths(raw_stdout: bytes, repository_root: Path, skip_label: str) -> list[Path]:
    """Turn a null-terminated git path stream into absolute paths.

    Args:
        raw_stdout: The ``-z`` git stdout bytes.
        repository_root: Repository root each relative path is joined to.
        skip_label: Word naming the source, shown in the skip message.

    Returns:
        Absolute paths; names whose bytes are not Unicode are logged and skipped.
    """
    resolved_paths: list[Path] = []
    for each_raw_path in raw_stdout.split(b"\x00"):
        if not each_raw_path:
            continue
        try:
            relative_path = each_raw_path.decode("utf-8")
        except UnicodeDecodeError:
            sys.stderr.write(
                f"code_rules_gate: skipping {skip_label} path with non-UTF-8 "
                f"filename: {each_raw_path!r}\n"
            )
            continue
        resolved_paths.append(repository_root / relative_path)
    return resolved_paths


def resolve_merge_base(repository_root: Path, base_reference: str) -> str:
    """Return the merge-base SHA between HEAD and *base_reference*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        base_reference: The git reference to merge-base against.

    Returns:
        The stripped merge-base SHA.

    Raises:
        SystemExit: When ``git merge-base`` returns non-zero.
    """
    stdout = _git_text_or_exit(
        repository_root,
        ["git", "merge-base", "HEAD", base_reference],
        f"code_rules_gate: git merge-base HEAD {base_reference} failed",
    )
    return stdout.strip()


def paths_from_git_staged(repository_root: Path) -> list[Path]:
    """Return absolute paths for every file in the staged index.

    Args:
        repository_root: Repository root used as the ``git -C`` target.

    Returns:
        Absolute paths for staged files, non-Unicode names skipped.

    Raises:
        SystemExit: When the staged name-only command returns non-zero.
    """
    raw_stdout = _git_bytes_or_exit(
        repository_root,
        list(ALL_GIT_DIFF_CACHED_NAME_ONLY_NULL_TERMINATED_COMMAND),
        "code_rules_gate: git diff --cached --name-only -z failed",
    )
    return _null_separated_paths(raw_stdout, repository_root, "staged")


def paths_from_git_diff(
    repository_root: Path,
    base_reference: str,
    resolved_merge_base: str | None = None,
) -> list[Path]:
    """Return absolute paths for every file changed since *base_reference*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        base_reference: The git reference to merge-base against.
        resolved_merge_base: Pre-resolved merge-base SHA; when omitted, the
            merge base of HEAD and *base_reference* is resolved here.

    Returns:
        Absolute paths changed since the merge-base of HEAD and *base_reference*.

    Raises:
        SystemExit: When the diff name-only command returns non-zero.
    """
    merge_base = (
        resolved_merge_base
        if resolved_merge_base is not None
        else resolve_merge_base(repository_root, base_reference)
    )
    diff_command = [
        *ALL_GIT_DIFF_NAME_ONLY_NULL_TERMINATED_COMMAND_PREFIX,
        f"{merge_base}..HEAD",
    ]
    raw_stdout = _git_bytes_or_exit(
        repository_root,
        diff_command,
        "code_rules_gate: git diff --name-only -z failed",
    )
    return _null_separated_paths(raw_stdout, repository_root, "diff")


def paths_from_git_untracked(repository_root: Path) -> list[Path]:
    """Return absolute paths for every untracked, non-ignored file.

    Args:
        repository_root: Repository root used as the ``git -C`` target.

    Returns:
        Absolute paths git reports as untracked and not git-ignored.

    Raises:
        SystemExit: When ``git ls-files --others`` returns non-zero.
    """
    raw_stdout = _git_bytes_or_exit(
        repository_root,
        list(ALL_GIT_LS_FILES_UNTRACKED_NULL_TERMINATED_COMMAND),
        "code_rules_gate: git ls-files --others --exclude-standard -z failed",
    )
    return _null_separated_paths(raw_stdout, repository_root, "untracked")


def _normalized_prefixes(all_prefixes: list[str]) -> list[str]:
    """Return the trimmed, slash-normalized, non-empty prefixes."""
    return [
        each_prefix.strip().replace("\\", "/").rstrip("/")
        for each_prefix in all_prefixes
        if each_prefix.strip()
    ]


def _relative_posix_under_root(file_path: Path, resolved_root: Path) -> str | None:
    """Return *file_path* relative to *resolved_root* as POSIX text, or None."""
    try:
        return file_path.resolve().relative_to(resolved_root).as_posix()
    except ValueError:
        return None


def _matches_any_prefix(relative_posix: str, all_normalized_prefixes: list[str]) -> bool:
    """Return True when *relative_posix* equals or nests under a prefix."""
    return any(
        relative_posix == each_prefix or relative_posix.startswith(each_prefix + "/")
        for each_prefix in all_normalized_prefixes
    )


def filter_paths_under_prefixes(
    all_file_paths: list[Path],
    repository_root: Path,
    all_prefixes: list[str],
) -> list[Path]:
    """Filter *all_file_paths* to entries under the supplied prefixes.

    Args:
        all_file_paths: Resolved file paths to filter.
        repository_root: Repository root the relative paths are measured against.
        all_prefixes: Repo-relative POSIX prefixes; a path passes when it
            equals a prefix or is nested beneath it.

    Returns:
        The matching subset, or the input unchanged when no prefix is given.
    """
    all_normalized_prefixes = _normalized_prefixes(all_prefixes)
    if not all_normalized_prefixes:
        return all_file_paths
    resolved_root = repository_root.resolve()
    filtered: list[Path] = []
    for each_path in all_file_paths:
        relative_posix = _relative_posix_under_root(each_path, resolved_root)
        if relative_posix is None:
            continue
        if _matches_any_prefix(relative_posix, all_normalized_prefixes):
            filtered.append(each_path)
    return filtered


def is_staged_file_newly_added(repository_root: Path, relative_path_posix: str) -> bool:
    """Check whether *relative_path_posix* is newly added in the staged diff.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to inspect.

    Returns:
        True when the first non-empty name-status line begins with ``A``.

    Raises:
        SystemExit: When the staged name-status command returns non-zero.
    """
    stdout = _git_text_or_exit(
        repository_root,
        ["git", "diff", "--cached", "--name-status", "--", relative_path_posix],
        (f"code_rules_gate: git diff --cached --name-status failed for {relative_path_posix}"),
    )
    for each_line in stdout.splitlines():
        stripped_line = each_line.strip()
        if stripped_line:
            return stripped_line.startswith(GIT_NAME_STATUS_ADDED_PREFIX)
    return False


def staged_file_line_count(repository_root: Path, relative_path_posix: str) -> int:
    """Return the staged-blob line count for *relative_path_posix*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path of the staged file.

    Returns:
        The staged content line count, or zero when the blob is empty.

    Raises:
        SystemExit: When ``git show :<path>`` returns non-zero.
    """
    staged_content = _git_text_or_exit(
        repository_root,
        ["git", "show", f":{relative_path_posix}"],
        f"code_rules_gate: git show :{relative_path_posix} failed",
    )
    if not staged_content:
        return 0
    return len(staged_content.splitlines())


def staged_unified_diff_text(repository_root: Path, relative_path_posix: str) -> str:
    """Return the staged unified-zero diff text for one file.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to diff.

    Returns:
        The ``git diff --cached --unified=0`` stdout for the file.

    Raises:
        SystemExit: When the staged diff command returns non-zero.
    """
    return _git_text_or_exit(
        repository_root,
        ["git", "diff", "--cached", "--unified=0", "--", relative_path_posix],
        (f"code_rules_gate: git diff --cached --unified=0 failed for {relative_path_posix}"),
    )
