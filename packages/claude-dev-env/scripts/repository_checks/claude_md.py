"""CLAUDE.md reference checks for committed trees."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

from policy_lint.config.constants import PATH_SEPARATOR, UTF8_ENCODING

from repository_checks.config.constants import (
    CHECK_ID_CLAUDE_MD_ORPHANS,
    CLAUDE_MD_CONSTANTS_MODULE_NAME,
    CLAUDE_MD_MISSING_FILE_MESSAGE_TEMPLATE,
    CLAUDE_MD_SCAN_MODULE_NAME,
    WINDOWS_PATH_SEPARATOR,
)
from repository_checks.hook_modules import load_hooks_module
from repository_checks.models import RepositoryFinding


def collect_claude_md_orphan_findings(
    repository_root: Path, all_tracked_paths: Sequence[str]
) -> list[RepositoryFinding]:
    """Return missing CLAUDE.md references in the tracked tree.

    Args:
        repository_root: Git repository root.
        all_tracked_paths: Repository-relative tracked paths.

    Returns:
        Findings for references whose files are absent.
    """
    subtree_scan = load_hooks_module(CLAUDE_MD_SCAN_MODULE_NAME)
    claude_md_constants = load_hooks_module(CLAUDE_MD_CONSTANTS_MODULE_NAME)
    all_findings: list[RepositoryFinding] = []
    for each_relative_path in all_tracked_paths:
        all_findings.extend(
            find_orphan_findings_for_path(
                repository_root,
                each_relative_path,
                subtree_scan,
                claude_md_constants,
            )
        )
    return all_findings


def find_orphan_findings_for_path(
    repository_root: Path,
    relative_path: str,
    subtree_scan: ModuleType,
    claude_md_constants: ModuleType,
) -> list[RepositoryFinding]:
    """Return missing files named by one CLAUDE.md file.

    Args:
        repository_root: Git repository root.
        relative_path: Repository-relative path to inspect.
        subtree_scan: Existing reference detector module.
        claude_md_constants: Existing detector constants module.

    Returns:
        Findings for referenced files that are absent from the scan root.
    """
    if Path(relative_path).name != claude_md_constants.CLAUDE_MD_FILENAME:
        return []
    absolute_path = repository_root / relative_path
    if not absolute_path.is_file():
        return []
    return _find_orphans_in_claude_md(absolute_path, relative_path, subtree_scan)


def _find_orphans_in_claude_md(
    absolute_path: Path,
    relative_path: str,
    subtree_scan: ModuleType,
) -> list[RepositoryFinding]:
    content = absolute_path.read_text(encoding=UTF8_ENCODING)
    claude_md_directory = absolute_path.parent
    subtree_root = _subtree_root_for(claude_md_directory)
    subtree_root.stat()
    deque(subtree_root.rglob("*"), maxlen=0)
    all_missing_filenames = subtree_scan.find_missing_filenames(
        content, claude_md_directory
    )
    return _build_findings(relative_path, all_missing_filenames)


def _subtree_root_for(claude_md_directory: Path) -> Path:
    parent_directory = claude_md_directory.parent
    if parent_directory == claude_md_directory:
        return claude_md_directory
    return parent_directory


def _build_findings(
    relative_path: str, all_missing_filenames: Sequence[str]
) -> list[RepositoryFinding]:
    return [
        RepositoryFinding(
            CHECK_ID_CLAUDE_MD_ORPHANS,
            relative_path.replace(WINDOWS_PATH_SEPARATOR, PATH_SEPARATOR),
            CLAUDE_MD_MISSING_FILE_MESSAGE_TEMPLATE.format(filename=each_filename),
        )
        for each_filename in all_missing_filenames
    ]
