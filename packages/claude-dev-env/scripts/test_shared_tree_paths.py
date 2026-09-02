"""Behavioral tests for shared-tree directory resolution."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import shared_tree_paths  # noqa: E402
from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    CLAUDE_CONFIG_DIR_ENV_VAR,
    PROCESS_TREE_DIRECTORY_NAME,
    PROCESS_TREE_KILL_MODULE_FILENAME,
    SCRIPTS_DIRECTORY_NAME,
    SHARED_PACKAGE_DIRECTORY_NAME,
)


def _create_directory_link(*, from_link: Path, to_target: Path) -> None:
    if sys.platform.startswith("win32"):
        importlib.import_module("_winapi").CreateJunction(
            str(to_target), str(from_link)
        )
        return
    try:
        os.symlink(to_target, from_link, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is not available")


def _build_junction_scripts_layout(tmp_path: Path) -> Path:
    real_scripts_directory = tmp_path / "real" / SCRIPTS_DIRECTORY_NAME
    real_scripts_directory.mkdir(parents=True)
    (real_scripts_directory / "runner.py").write_text("", encoding="utf-8")
    managed_root = tmp_path / "root"
    managed_root.mkdir()
    _create_directory_link(
        from_link=managed_root / SCRIPTS_DIRECTORY_NAME,
        to_target=real_scripts_directory,
    )
    return managed_root / SCRIPTS_DIRECTORY_NAME / "runner.py"


def _write_process_tree_kill_stub(from_root: Path) -> Path:
    scripts_directory = (
        from_root
        / SHARED_PACKAGE_DIRECTORY_NAME
        / PROCESS_TREE_DIRECTORY_NAME
        / SCRIPTS_DIRECTORY_NAME
    )
    scripts_directory.mkdir(parents=True)
    (scripts_directory / PROCESS_TREE_KILL_MODULE_FILENAME).write_text(
        "", encoding="utf-8"
    )
    return scripts_directory


def test_junction_scripts_dir_finds_shared_tree_on_unresolved_parent(
    tmp_path: Path,
) -> None:
    module_file = _build_junction_scripts_layout(tmp_path)
    expected_scripts_directory = _write_process_tree_kill_stub(tmp_path / "root")
    resolved_scripts_directory = (
        shared_tree_paths.resolve_shared_process_tree_scripts_directory(
            module_file, all_environment={}
        )
    )
    assert resolved_scripts_directory == expected_scripts_directory


def test_resolved_parent_is_used_when_link_side_has_no_shared_tree(
    tmp_path: Path,
) -> None:
    module_file = _build_junction_scripts_layout(tmp_path)
    expected_scripts_directory = _write_process_tree_kill_stub(tmp_path / "real")
    resolved_scripts_directory = (
        shared_tree_paths.resolve_shared_process_tree_scripts_directory(
            module_file, all_environment={}
        )
    )
    assert resolved_scripts_directory == expected_scripts_directory


def test_configured_root_is_used_when_neither_parent_holds_the_module(
    tmp_path: Path,
) -> None:
    module_file = _build_junction_scripts_layout(tmp_path)
    configured_root = tmp_path / "configured"
    expected_scripts_directory = _write_process_tree_kill_stub(configured_root)
    resolved_scripts_directory = (
        shared_tree_paths.resolve_shared_process_tree_scripts_directory(
            module_file,
            all_environment={
                CLAUDE_CONFIG_DIR_ENV_VAR: str(configured_root)
            },
        )
    )
    assert resolved_scripts_directory == expected_scripts_directory


def test_unresolved_parent_wins_when_configured_root_also_holds_the_module(
    tmp_path: Path,
) -> None:
    module_file = _build_junction_scripts_layout(tmp_path)
    expected_scripts_directory = _write_process_tree_kill_stub(tmp_path / "root")
    configured_root = tmp_path / "configured"
    _write_process_tree_kill_stub(configured_root)
    resolved_scripts_directory = (
        shared_tree_paths.resolve_shared_process_tree_scripts_directory(
            module_file,
            all_environment={
                CLAUDE_CONFIG_DIR_ENV_VAR: str(configured_root)
            },
        )
    )
    assert resolved_scripts_directory == expected_scripts_directory


def test_missing_module_returns_unresolved_candidate(tmp_path: Path) -> None:
    module_file = _build_junction_scripts_layout(tmp_path)
    expected_scripts_directory = (
        tmp_path
        / "root"
        / SHARED_PACKAGE_DIRECTORY_NAME
        / PROCESS_TREE_DIRECTORY_NAME
        / SCRIPTS_DIRECTORY_NAME
    )
    resolved_scripts_directory = (
        shared_tree_paths.resolve_shared_process_tree_scripts_directory(
            module_file, all_environment={}
        )
    )
    assert resolved_scripts_directory == expected_scripts_directory
    assert not (
        expected_scripts_directory / PROCESS_TREE_KILL_MODULE_FILENAME
    ).is_file()
