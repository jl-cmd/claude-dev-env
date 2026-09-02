"""Resolve directories inside the installed shared tree."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from dev_env_scripts_constants.grok_worker_constants import (
    CLAUDE_CONFIG_DIR_ENV_VAR,
    PROCESS_TREE_DIRECTORY_NAME,
    PROCESS_TREE_KILL_MODULE_FILENAME,
    SCRIPTS_DIRECTORY_NAME,
    SHARED_PACKAGE_DIRECTORY_NAME,
)


def _process_tree_scripts_directory(from_root: Path) -> Path:
    return (
        from_root
        / SHARED_PACKAGE_DIRECTORY_NAME
        / PROCESS_TREE_DIRECTORY_NAME
        / SCRIPTS_DIRECTORY_NAME
    )


def _has_process_tree_kill_module(from_directory: Path) -> bool:
    return (from_directory / PROCESS_TREE_KILL_MODULE_FILENAME).is_file()


def resolve_shared_process_tree_scripts_directory(
    module_file: str | Path,
    all_environment: Mapping[str, str],
) -> Path:
    """Return the first process-tree scripts directory that holds the kill helper.

    ::

        scripts dir is a junction; the kill helper sits beside the un-resolved parent
        ok:   Path(module_file).absolute().parent.parent then the _shared scripts dir
        flag: Path(module_file).resolve().parents[1] walks the junction and misses it

    Tries the un-resolved parent first, then the configured managed root, then
    the resolved parent. When none hold the helper, return the un-resolved
    candidate so import failure names a readable path.

    Args:
        module_file: Path of the importing module (``__file__``).
        all_environment: Mapping that may hold ``CLAUDE_CONFIG_DIR``.

    Returns:
        Directory that should hold ``process_tree_kill.py``.
    """
    un_resolved_candidate = _process_tree_scripts_directory(
        Path(module_file).absolute().parent.parent
    )
    all_candidates = [un_resolved_candidate]
    configured_root_text = all_environment.get(
        CLAUDE_CONFIG_DIR_ENV_VAR, ""
    ).strip()
    if configured_root_text:
        all_candidates.append(
            _process_tree_scripts_directory(Path(configured_root_text))
        )
    all_candidates.append(
        _process_tree_scripts_directory(Path(module_file).resolve().parents[1])
    )
    for each_candidate in all_candidates:
        if _has_process_tree_kill_module(each_candidate):
            return each_candidate
    return un_resolved_candidate
