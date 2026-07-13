"""Resolve a CLAUDE.md's scan root and find the referenced files absent from it.

The scan root is the CLAUDE.md directory's parent, covering the directory, its
subdirectories, and its siblings. A bounded walk collects the file basenames;
when the budget truncates the walk, a direct ``rglob`` probe resolves any name
the partial set missed, so a truncated slice never reports a present file as
missing.
"""

from pathlib import Path

from claude_md_orphan_file_blocker_parts.references import (
    find_referenced_filenames,
    find_run_command_filenames,
)

from hooks_constants.claude_md_orphan_file_blocker_constants import (
    ALL_NOISE_DIRECTORY_NAMES,
    MAX_ORPHAN_FILE_ISSUES,
    MAX_SUBTREE_FILES_SCANNED,
)


def _resolve_scan_root(claude_md_directory: Path) -> Path:
    """Return the directory whose subtree bounds the filename existence search.

    Args:
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        The CLAUDE.md directory's parent, or the directory itself when it has no
        distinct parent.
    """
    parent_directory = claude_md_directory.parent
    if parent_directory == claude_md_directory:
        return claude_md_directory
    return parent_directory


class _SubtreeScan:
    """The basenames a bounded subtree walk collected and whether it ran complete.

    Attributes:
        all_basenames: Each file basename the walk reached.
        was_scan_complete: True when the walk visited the whole subtree within the
            budget, so ``all_basenames`` is authoritative.
    """

    def __init__(self, all_basenames: set[str], was_scan_complete: bool) -> None:
        self.all_basenames = all_basenames
        self.was_scan_complete = was_scan_complete


def _is_under_noise_directory(scan_root: Path, candidate_path: Path) -> bool:
    """Return whether *candidate_path* lies inside a pruned noise directory.

    Args:
        scan_root: The directory the walk descends from.
        candidate_path: A path the walk yielded under the scan root.

    Returns:
        True when any path segment below *scan_root* names a noise directory.
    """
    try:
        relative_segments = candidate_path.relative_to(scan_root).parts
    except ValueError:
        relative_segments = candidate_path.parts
    return any(each_segment in ALL_NOISE_DIRECTORY_NAMES for each_segment in relative_segments)


def _is_countable_file(candidate_path: Path) -> bool:
    """Return whether *candidate_path* is a readable regular file.

    Args:
        candidate_path: A path the walk yielded.

    Returns:
        True when the path is a file; a per-entry stat error reads as False.
    """
    try:
        return candidate_path.is_file()
    except OSError:
        return False


def _scan_subtree_basenames(scan_root: Path) -> _SubtreeScan:
    """Return the bounded basename scan of *scan_root*, skipping unreadable entries.

    Args:
        scan_root: The directory whose subtree bounds the existence search.

    Returns:
        The collected basenames paired with the scan-completeness flag.
    """
    all_basenames: set[str] = set()
    scanned_count = 0
    for each_path in scan_root.rglob("*"):
        if _is_under_noise_directory(scan_root, each_path):
            continue
        if not _is_countable_file(each_path):
            continue
        all_basenames.add(each_path.name)
        scanned_count += 1
        if scanned_count >= MAX_SUBTREE_FILES_SCANNED:
            return _SubtreeScan(all_basenames, was_scan_complete=False)
    return _SubtreeScan(all_basenames, was_scan_complete=True)


def _filename_exists_under(scan_root: Path, filename: str) -> bool:
    """Return whether a file with basename *filename* exists anywhere under root.

    Args:
        scan_root: The directory whose subtree bounds the existence search.
        filename: The bare basename to look for.

    Returns:
        True when at least one matching file is reachable under the scan root.
    """
    for each_match in scan_root.rglob(filename):
        if _is_under_noise_directory(scan_root, each_match):
            continue
        if _is_countable_file(each_match):
            return True
    return False


def _present_referenced_filenames(all_referenced_filenames: list[str], scan_root: Path) -> set[str]:
    """Return the referenced filenames that exist under the scan root.

    Args:
        all_referenced_filenames: The bare filenames a CLAUDE.md table names.
        scan_root: The directory whose subtree bounds the existence search.

    Returns:
        The subset of *all_referenced_filenames* that resolve to an existing file.
    """
    subtree_scan = _scan_subtree_basenames(scan_root)
    present_filenames: set[str] = set()
    for each_filename in all_referenced_filenames:
        if each_filename in subtree_scan.all_basenames:
            present_filenames.add(each_filename)
            continue
        if subtree_scan.was_scan_complete:
            continue
        if _filename_exists_under(scan_root, each_filename):
            present_filenames.add(each_filename)
    return present_filenames


def find_missing_filenames(content: str, claude_md_directory: Path) -> list[str]:
    """Return the referenced filenames absent from the CLAUDE.md's scan root.

    Args:
        content: The CLAUDE.md content being written.
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        Each referenced filename with no matching file under the scan root.
    """
    referenced_filenames = find_referenced_filenames(content) + find_run_command_filenames(content)
    if not referenced_filenames:
        return []
    scan_root = _resolve_scan_root(claude_md_directory)
    try:
        present_filenames = _present_referenced_filenames(referenced_filenames, scan_root)
    except OSError:
        return []
    missing_filenames: list[str] = []
    already_reported: set[str] = set()
    for each_filename in referenced_filenames:
        if each_filename in already_reported:
            continue
        if each_filename in present_filenames:
            continue
        already_reported.add(each_filename)
        missing_filenames.append(each_filename)
        if len(missing_filenames) >= MAX_ORPHAN_FILE_ISSUES:
            break
    return missing_filenames
