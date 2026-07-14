"""Build the orphan scan plan for a Write, Edit, or MultiEdit of a CLAUDE.md.

For a Write the plan scans the full new content with no baseline. For an Edit or
MultiEdit it scans the reconstructed post-edit file and records the orphans the
file already held, so a pre-existing orphan on an untouched line is excluded and
only an orphan the edit introduces is reported.
"""

from pathlib import Path

from claude_md_orphan_file_blocker_parts.subtree_scan import find_missing_filenames

from hooks_constants.claude_md_orphan_file_blocker_constants import (
    MAX_ORPHAN_FILE_ISSUES,
)
from hooks_constants.multi_edit_reconstruction import (
    apply_edits,
    edits_for_tool,
)


def _read_existing_file_content(file_path: str) -> str | None:
    """Return the current on-disk content of *file_path*, or None when unreadable.

    Args:
        file_path: The path of the file the edit targets.

    Returns:
        The file's text, or None when the file is missing or cannot be decoded.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _edit_fragments(all_edits: list[dict]) -> list[str]:
    """Return each MultiEdit ``new_string`` fragment present as a non-empty string.

    Args:
        all_edits: The MultiEdit ``edits`` list.

    Returns:
        Every ``new_string`` value that is a non-empty string, in list order.
    """
    all_fragments: list[str] = []
    for each_edit in all_edits:
        if not isinstance(each_edit, dict):
            continue
        new_string = each_edit.get("new_string", "")
        if isinstance(new_string, str) and new_string:
            all_fragments.append(new_string)
    return all_fragments


class _OrphanScanPlan:
    """The contents to scan for orphans and the pre-existing orphans to exclude.

    Attributes:
        candidate_contents: Each content string whose table rows are scanned.
        baseline_missing_filenames: The orphan filenames the file already held
            before this edit; reporting excludes them.
    """

    def __init__(
        self, all_candidate_contents: list[str], all_baseline_missing_filenames: set[str]
    ) -> None:
        self.candidate_contents = all_candidate_contents
        self.baseline_missing_filenames = all_baseline_missing_filenames


def build_orphan_scan_plan(
    tool_name: str, tool_input: dict, file_path: str, claude_md_directory: Path
) -> _OrphanScanPlan:
    """Return the contents to scan and the pre-existing orphans to exclude.

    Args:
        tool_name: The intercepted tool — ``Write``, ``Edit``, or ``MultiEdit``.
        tool_input: The tool's input payload.
        file_path: The destination path of the write or edit.
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        The scan plan pairing candidate contents with the baseline orphan set.
    """
    if tool_name == "Write":
        content = tool_input.get("content", "")
        candidate_contents = [content] if isinstance(content, str) and content else []
        return _OrphanScanPlan(candidate_contents, set())
    all_edits = edits_for_tool(tool_name, tool_input)
    existing_content = _read_existing_file_content(file_path)
    if existing_content is None:
        return _OrphanScanPlan(_edit_fragments(all_edits), set())
    baseline_missing = set(find_missing_filenames(existing_content, claude_md_directory))
    return _OrphanScanPlan([apply_edits(existing_content, all_edits)], baseline_missing)


def collect_missing_filenames(scan_plan: _OrphanScanPlan, claude_md_directory: Path) -> list[str]:
    """Return every orphan filename the scan plan introduces, excluding baselines.

    Args:
        scan_plan: The candidate contents to scan paired with the baseline orphan
            set to exclude.
        claude_md_directory: The directory that holds the target CLAUDE.md.

    Returns:
        Each introduced orphan filename in first-seen order with duplicates
        removed, capped at the issue budget.
    """
    all_candidate_missing: list[str] = []
    for each_content in scan_plan.candidate_contents:
        all_candidate_missing.extend(find_missing_filenames(each_content, claude_md_directory))
    missing_filenames: list[str] = []
    already_reported: set[str] = set()
    for each_filename in all_candidate_missing:
        if each_filename in scan_plan.baseline_missing_filenames:
            continue
        if each_filename in already_reported:
            continue
        already_reported.add(each_filename)
        missing_filenames.append(each_filename)
        if len(missing_filenames) >= MAX_ORPHAN_FILE_ISSUES:
            break
    return missing_filenames
