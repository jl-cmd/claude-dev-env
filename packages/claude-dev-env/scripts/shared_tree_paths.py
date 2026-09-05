"""Resolve a scripts directory inside the installed shared tree.

An install can place a managed directory behind a directory junction. Path
resolution walks that link, so a parent computed from the resolved path
names the link target's parent, where the shared tree does not sit.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from dev_env_scripts_constants.shared_tree_constants import (
    AGENTS_DIRECTORY_SUFFIX,
    CLAUDE_CONFIG_DIR_ENV_VAR,
    DEFAULT_MANAGED_ROOT_NAME,
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


def _linked_managed_root(module_path: Path, anchor_depth: int) -> Path | None:
    """Resolve the managed root whose scripts pointer targets this installed tree.

    Args:
        module_path: The module path inside the managed scripts tree.
        anchor_depth: Parent index of the package or agents root.

    Returns:
        The paired Claude root when its scripts pointer resolves to this tree.
    """
    package_root = module_path.resolve().parents[anchor_depth]
    if not package_root.name.endswith(AGENTS_DIRECTORY_SUFFIX):
        return None
    managed_name = package_root.name.removesuffix(AGENTS_DIRECTORY_SUFFIX) or DEFAULT_MANAGED_ROOT_NAME
    managed_root = package_root.parent / managed_name
    linked_scripts = managed_root / SCRIPTS_DIRECTORY_NAME
    if not linked_scripts.is_dir():
        return None
    if linked_scripts.resolve() != package_root / SCRIPTS_DIRECTORY_NAME:
        return None
    return managed_root


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

    Tries the un-resolved parent first, then a verified installed scripts
    pointer, then the configured managed root and the resolved parent. When none holds the marker, returns the
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
    linked_root = _linked_managed_root(module_path, anchor_depth)
    if linked_root is not None:
        all_candidates.append(_shared_scripts_directory(linked_root, shared_subpackage_name))
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
