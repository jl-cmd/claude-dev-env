"""Behavior tests for plugin data directory cleanup."""

from __future__ import annotations

import importlib.util
import stat
from pathlib import Path


HOOK_DIRECTORY = Path(__file__).parent
HOOK_SPEC = importlib.util.spec_from_file_location(
    "plugin_data_dir_cleanup",
    HOOK_DIRECTORY / "plugin_data_dir_cleanup.py",
)
assert HOOK_SPEC is not None
assert HOOK_SPEC.loader is not None
HOOK_MODULE = importlib.util.module_from_spec(HOOK_SPEC)
HOOK_SPEC.loader.exec_module(HOOK_MODULE)


def _configure_plugin_data_directory(plugin_data_directory: Path) -> None:
    HOOK_MODULE.__dict__["PLUGINS_DATA_DIRECTORY"] = str(plugin_data_directory)
    HOOK_MODULE.__dict__["AFFECTED_PLUGIN_DIRECTORIES"] = ["sample-plugin"]


def test_main_removes_empty_plugin_data_directory(tmp_path: Path) -> None:
    plugin_data_directory = tmp_path / "plugin-data"
    plugin_data_directory.mkdir()
    empty_plugin_directory = plugin_data_directory / "sample-plugin"
    empty_plugin_directory.mkdir()
    _configure_plugin_data_directory(plugin_data_directory)

    HOOK_MODULE.main()

    assert not empty_plugin_directory.exists()


def test_main_keeps_plugin_data_directory_with_files(tmp_path: Path) -> None:
    plugin_data_directory = tmp_path / "plugin-data"
    plugin_data_directory.mkdir()
    retained_plugin_directory = plugin_data_directory / "sample-plugin"
    retained_plugin_directory.mkdir()
    (retained_plugin_directory / "state.json").write_text("{}", encoding="utf-8")
    _configure_plugin_data_directory(plugin_data_directory)

    HOOK_MODULE.main()

    assert retained_plugin_directory.is_dir()


def test_main_keeps_read_only_plugin_data_directory_with_files(
    tmp_path: Path,
) -> None:
    plugin_data_directory = tmp_path / "plugin-data"
    plugin_data_directory.mkdir()
    retained_plugin_directory = plugin_data_directory / "sample-plugin"
    retained_plugin_directory.mkdir()
    state_file = retained_plugin_directory / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    state_file.chmod(stat.S_IREAD)
    _configure_plugin_data_directory(plugin_data_directory)

    HOOK_MODULE.main()

    assert retained_plugin_directory.is_dir()
    state_file.chmod(stat.S_IREAD | stat.S_IWRITE)
