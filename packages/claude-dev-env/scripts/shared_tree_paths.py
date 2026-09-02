"""Resolve a scripts directory inside the installed shared tree.

An install can place a managed directory behind a directory junction. Path
resolution walks that link, so a parent computed from the resolved path
names the link target's parent, where the shared tree does not sit.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from dev_env_scripts_constants.shared_tree_constants import (
    CLAUDE_CONFIG_DIR_ENV_VAR,
    PROCESS_TREE_DIRECTORY_NAME,
    PROCESS_TREE_KILL_MODULE_FILENAME,
    SCRIPTS_DIRECTORY_NAME,
    SHARED_PACKAGE_DIRECTORY_NAME,
)


def _shared_scripts_directory(from_root: Path, shared_subpackage_name: str) -> Path:
    """Return the scripts directory one named sub-package holds under a root."""
    return (
        from_root
        / SHARED_PACKAGE_DIRECTORY_NAME
        / shared_subpackage_name
        / SCRIPTS_DIRECTORY_NAME
    )


def resolve_shared_scripts_directory(
    module_file: str | Path,
    all_environment: Mapping[str, str],
    shared_subpackage_name: str,
    marker_filename: str,
    anchor_depth: int,
) -> Path:
    """Return the first shared scripts directory that holds the marker file.

    ::

        the managed scripts directory is a junction
        ok:   an un-resolved parent keeps the link side, where _shared sits
        flag: a resolved parent walks the link and misses _shared entirely

    Tries the un-resolved parent first, then the configured managed root,
    then the resolved parent. When none holds the marker, returns the
    un-resolved candidate, so an import failure names a readable path.

    Args:
        module_file: Path of the importing module (``__file__``).
        all_environment: Mapping that may hold ``CLAUDE_CONFIG_DIR``.
        shared_subpackage_name: Directory under ``_shared`` to resolve.
        marker_filename: File whose presence marks the right directory.
        anchor_depth: Parent levels above the module to treat as the root.

    Returns:
        Directory that should hold the marker file.
    """
    module_path = Path(module_file)
    un_resolved_candidate = _shared_scripts_directory(
        module_path.absolute().parents[anchor_depth], shared_subpackage_name
    )
    all_candidates = [un_resolved_candidate]
    configured_root_text = all_environment.get(CLAUDE_CONFIG_DIR_ENV_VAR, "").strip()
    if configured_root_text:
        all_candidates.append(
            _shared_scripts_directory(Path(configured_root_text), shared_subpackage_name)
        )
    all_candidates.append(
        _shared_scripts_directory(
            module_path.resolve().parents[anchor_depth], shared_subpackage_name
        )
    )
    for each_candidate in all_candidates:
        if (each_candidate / marker_filename).is_file():
            return each_candidate
    return un_resolved_candidate


def resolve_shared_process_tree_scripts_directory(
    module_file: str | Path,
    all_environment: Mapping[str, str],
) -> Path:
    """Return the process-tree scripts directory that holds the kill helper.

    Names the process-tree sub-package for a caller sitting one level under
    the installed root, such as a script in the managed ``scripts`` directory.

    Args:
        module_file: Path of the importing module (``__file__``).
        all_environment: Mapping that may hold ``CLAUDE_CONFIG_DIR``.

    Returns:
        Directory that should hold ``process_tree_kill.py``.
    """
    return resolve_shared_scripts_directory(
        module_file,
        all_environment,
        PROCESS_TREE_DIRECTORY_NAME,
        PROCESS_TREE_KILL_MODULE_FILENAME,
        1,
    )
