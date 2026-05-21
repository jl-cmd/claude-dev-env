"""Shared exemption rules for the .md blocker and its post-write companion.

Both `md_to_html_blocker.py` (PreToolUse) and `md_to_html_companion.py`
(PostToolUse) must agree on which file paths bypass the .md → .html policy.
This module is the single source of truth for that decision.
"""

import os
import sys
from pathlib import Path, PureWindowsPath


_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.md_to_html_blocker_constants import (  # noqa: E402
    ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES,
    ALL_EXEMPT_ANYWHERE_FILENAMES_LOWER,
    ALL_EXEMPT_HOME_DIRECTORY_PATH_PREFIXES,
    ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS,
    ALL_EXEMPT_ROOT_FILENAMES_LOWER,
    CLAUDE_DEV_ENV_REPO_NAME_SEGMENT,
    CLAUDE_DIRECTORY_PATH_PREFIX,
    CLAUDE_DIRECTORY_SEGMENT_MARKER,
    MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR,
    PACKAGES_TOP_LEVEL_SEGMENT,
    PLUGIN_DIRECTORY_PATH_PREFIX,
    PLUGIN_DIRECTORY_SEGMENT_MARKER,
    PLUGIN_ROOT_MARKER_DIRECTORY_NAME,
    REPO_ROOT_MARKER_NAME,
    RESOLVED_HOME_DIRECTORY_LOWER,
    RESOLVED_TEMP_DIRECTORY_PATH_PREFIX,
)


def is_exempt_path(file_path: str) -> bool:
    """Return True when the .md file path is exempt from the blocker policy.

    Exemption sources, in order of evaluation:
    - Any segment under `.claude/` or `.claude-plugin/` (case-insensitive)
    - Basename in `ALL_EXEMPT_ANYWHERE_FILENAMES` (e.g. SKILL.md)
    - Anchored under `packages/claude-dev-env/<one of
      ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES>/...` (docs, rules,
      system-prompts source files in this repo)
    - Path segment in `ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS` (agents/skills/commands)
    - Canonical path under a home-relative exempt directory
      (`ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES`)
    - Canonical path under the OS temp directory
    - Ancestor directory contains `.claude-plugin/` (plugin-root marker walk)
    - Basename in `ALL_EXEMPT_ROOT_FILENAMES` and directory is a repo root

    Args:
        file_path: Raw file path from the hook payload. May contain tilde,
            backslashes, or be relative.

    Returns:
        True when the path is exempt, False when the policy applies.
    """
    expanded_path = os.path.expanduser(file_path)
    normalized = os.path.normpath(expanded_path).replace("\\", "/")
    lower_normalized = normalized.lower()
    if (
        CLAUDE_DIRECTORY_SEGMENT_MARKER in lower_normalized
        or lower_normalized.startswith(CLAUDE_DIRECTORY_PATH_PREFIX)
    ):
        return True
    if (
        PLUGIN_DIRECTORY_SEGMENT_MARKER in lower_normalized
        or lower_normalized.startswith(PLUGIN_DIRECTORY_PATH_PREFIX)
    ):
        return True
    basename_lower = os.path.basename(normalized).lower()
    if basename_lower in ALL_EXEMPT_ANYWHERE_FILENAMES_LOWER:
        return True
    if _is_under_claude_dev_env_source_subdirectory(expanded_path, lower_normalized):
        return True
    if _has_plugin_directory_segment(lower_normalized):
        return True
    canonical_normalized_path = os.path.realpath(expanded_path).replace("\\", "/")
    canonical_lower_path = canonical_normalized_path.lower()
    if _is_under_exempt_home_directory(canonical_lower_path):
        return True
    if canonical_lower_path.startswith(RESOLVED_TEMP_DIRECTORY_PATH_PREFIX):
        return True
    if _is_under_plugin_root_marker(canonical_normalized_path):
        return True
    if basename_lower in ALL_EXEMPT_ROOT_FILENAMES_LOWER:
        absolute_directory = _resolve_absolute_directory(normalized)
        if _is_repo_root_directory(absolute_directory):
            return True
    return False


def _resolve_absolute_directory(normalized_path: str) -> str:
    directory = os.path.dirname(normalized_path)
    if not directory or directory == ".":
        return os.getcwd()
    if os.path.isabs(directory):
        return directory
    return os.path.abspath(directory)


def _has_plugin_directory_segment(lower_normalized_path: str) -> bool:
    for each_directory_segment in ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS:
        segment_marker = f"/{each_directory_segment}/"
        if segment_marker in lower_normalized_path:
            return True
        if lower_normalized_path.startswith(f"{each_directory_segment}/"):
            return True
    return False


def _is_absolute_path_cross_platform(file_path: str) -> bool:
    """Detect absolute paths in both POSIX and Windows drive-letter forms.

    ``os.path.isabs`` is platform-dependent: on Linux/macOS it classifies a
    Windows drive-letter path like ``Y:\\repo\\foo`` as relative. The anchored
    source-subdirectory exemption must scan every starting segment for
    absolute paths regardless of host OS, so a path's absoluteness must be
    decided cross-platform.

    Args:
        file_path: Tilde-expanded file path.

    Returns:
        True when the path is absolute under POSIX rules or carries a Windows
        drive-letter root (``[A-Za-z]:[\\\\/]...``).
    """
    if os.path.isabs(file_path):
        return True
    return PureWindowsPath(file_path).is_absolute()


def _is_under_claude_dev_env_source_subdirectory(
    expanded_file_path: str, lower_normalized_path: str
) -> bool:
    """Anchored exemption for ``packages/claude-dev-env/<source-dir>/...``.

    The match requires segment-anchored matching at the start of the path
    (relative) or at the root of an absolute path. A nested path like
    ``notes/packages/claude-dev-env/docs/foo.md`` is NOT exempt — only the
    full three-segment anchor matches.

    Args:
        expanded_file_path: Tilde-expanded file path; ``os.path.isabs`` on
            this form classifies the path as absolute or relative on the
            current platform.
        lower_normalized_path: Same path lowercased and with separators
            normalized to forward slashes.

    Returns:
        True when the path is anchored under
        ``packages/claude-dev-env/<one of
        ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES>/``.
    """
    all_segments = [
        each_segment
        for each_segment in lower_normalized_path.split("/")
        if each_segment
    ]
    if not all_segments:
        return False
    if _is_absolute_path_cross_platform(expanded_file_path):
        starting_segment_index_options = list(range(len(all_segments)))
    else:
        starting_segment_index_options = [0]
    for each_starting_index in starting_segment_index_options:
        if (
            len(all_segments) >= each_starting_index + MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR
            and all_segments[each_starting_index] == PACKAGES_TOP_LEVEL_SEGMENT
            and all_segments[each_starting_index + 1] == CLAUDE_DEV_ENV_REPO_NAME_SEGMENT
            and all_segments[each_starting_index + 2] in ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES
        ):
            return True
    return False


def _is_under_plugin_root_marker(normalized_path: str) -> bool:
    directory = os.path.dirname(normalized_path)
    visited_directories: set[str] = set()
    while directory and directory not in visited_directories:
        visited_directories.add(directory)
        marker_path = os.path.join(directory, PLUGIN_ROOT_MARKER_DIRECTORY_NAME)
        if os.path.isdir(marker_path):
            return True
        parent_directory = os.path.dirname(directory)
        if parent_directory == directory:
            break
        directory = parent_directory
    return False


def _is_under_exempt_home_directory(lower_normalized_path: str) -> bool:
    if not RESOLVED_HOME_DIRECTORY_LOWER:
        return False
    for each_exempt_path_prefix in ALL_EXEMPT_HOME_DIRECTORY_PATH_PREFIXES:
        if lower_normalized_path.startswith(each_exempt_path_prefix):
            return True
    return False


def _is_repo_root_directory(directory_path: str) -> bool:
    git_marker_path = os.path.join(directory_path, REPO_ROOT_MARKER_NAME)
    return os.path.exists(git_marker_path)
