import importlib
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

import _claude_permissions_common as common_module
from _claude_permissions_common import (
    build_permission_rule,
    get_current_project_path,
    path_contains_glob_metacharacters,
    save_settings,
)
from config.claude_permissions_common_constants import DEFAULT_SETTINGS_FILE_MODE
import grant_project_claude_permissions as grant_module
import revoke_project_claude_permissions as revoke_module


def test_return_normalized_path_when_cwd_contains_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory_with_spaces = tmp_path / "dir with spaces"
    directory_with_spaces.mkdir()
    monkeypatch.chdir(directory_with_spaces)
    returned_project_path = get_current_project_path()
    expected_suffix = "/dir with spaces"
    assert returned_project_path.endswith(expected_suffix)
    assert "\\" not in returned_project_path
    built_rule = build_permission_rule("Edit", returned_project_path)
    assert built_rule.startswith("Edit(")
    assert built_rule.endswith("/.claude/**)")
    assert "dir with spaces" in built_rule


def test_raise_when_cwd_contains_glob_metacharacters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory_with_star = tmp_path / "weird[dir]"
    directory_with_star.mkdir()
    monkeypatch.chdir(directory_with_star)
    with pytest.raises(ValueError, match="glob metacharacters"):
        get_current_project_path()


def test_flag_glob_metacharacters_in_any_position() -> None:
    assert path_contains_glob_metacharacters("/home/user/[dir]/project")
    assert path_contains_glob_metacharacters("/home/user/project*")
    assert not path_contains_glob_metacharacters("/home/user/dir with spaces")


def test_save_settings_logs_when_temp_unlink_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A swallowed unlink in the finally block must surface to stderr.

    Forces a write success followed by os.replace failure so the temp file
    survives into the finally branch, then makes Path.unlink raise.
    """
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"existing": true}\n', encoding="utf-8")

    def failing_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("replace blocked by AV")

    def failing_unlink(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("temp file held by AV")

    with patch.object(common_module.os, "replace", failing_replace):
        with patch.object(Path, "unlink", failing_unlink):
            with pytest.raises(SystemExit):
                save_settings(settings_path, {"new_key": "value"})
    captured = capsys.readouterr()
    assert ".tmp" in captured.err
    assert "PermissionError" in captured.err or "held by AV" in captured.err


def test_save_settings_finally_skips_unlink_when_no_temp_was_created(
    tmp_path: Path,
) -> None:
    """When this invocation never created the temp file, finally must not unlink it."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"existing": true}\n', encoding="utf-8")

    unlink_call_paths: list[Path] = []
    original_unlink = Path.unlink

    def recording_unlink(self: Path, *args: object, **kwargs: object) -> None:
        unlink_call_paths.append(self)
        original_unlink(self, *args, **kwargs)

    def write_raises(*_args: object, **_kwargs: object) -> None:
        raise FileExistsError("another writer's temp")

    with patch.object(common_module, "write_atomically_with_mode", write_raises):
        with patch.object(Path, "unlink", recording_unlink):
            with pytest.raises(SystemExit):
                common_module.save_settings(settings_path, {"new_key": "value"})
    assert all(
        each_path.suffix != ".tmp"
        for each_path in unlink_call_paths
    ), (
        "finally must not unlink a temp file this invocation never created"
    )


def test_default_settings_file_mode_used_when_settings_file_missing(
    tmp_path: Path,
) -> None:
    """get_mode_to_preserve must fall back to DEFAULT_SETTINGS_FILE_MODE."""
    missing_settings_path = tmp_path / "no_such_file.json"
    returned_mode = common_module.get_mode_to_preserve(missing_settings_path)
    assert returned_mode == DEFAULT_SETTINGS_FILE_MODE


def test_is_valid_project_root_exported_from_consumer_modules(
    tmp_path: Path,
) -> None:
    """is_valid_project_root behaviour matches across both consumers.

    Grant and revoke each define their own local copy of the helper, so
    both copies must agree on the .git / .claude marker contract.
    """
    git_marker_project_root = tmp_path / "git_project"
    (git_marker_project_root / ".git").mkdir(parents=True)
    claude_marker_project_root = tmp_path / "claude_project"
    (claude_marker_project_root / ".claude").mkdir(parents=True)
    bare_directory = tmp_path / "no_marker"
    bare_directory.mkdir()
    assert grant_module.is_valid_project_root(git_marker_project_root) is True
    assert grant_module.is_valid_project_root(claude_marker_project_root) is True
    assert grant_module.is_valid_project_root(bare_directory) is False
    assert revoke_module.is_valid_project_root(git_marker_project_root) is True
    assert revoke_module.is_valid_project_root(claude_marker_project_root) is True
    assert revoke_module.is_valid_project_root(bare_directory) is False


def _reload_with_stale_config_cache(module_name: str) -> ModuleType:
    fake_submodule_name = "config.claude_permissions_common_constants"
    fake_parent_name = "config"
    sentinel_module_a = ModuleType(fake_parent_name)
    sentinel_module_b = ModuleType(fake_submodule_name)
    sys.modules[fake_parent_name] = sentinel_module_a
    sys.modules[fake_submodule_name] = sentinel_module_b
    try:
        target_module = sys.modules.get(module_name)
        if target_module is None:
            target_module = importlib.import_module(module_name)
        else:
            target_module = importlib.reload(target_module)
    finally:
        sys.modules.pop(fake_parent_name, None)
        sys.modules.pop(fake_submodule_name, None)
    return target_module


def test_grant_module_import_evicts_cached_config_submodules(
    tmp_path: Path,
) -> None:
    """grant_project_claude_permissions must evict cached `config.*` on import.

    Regression for loop1-2: without a defensive cache pop above sys.path.insert,
    a cached `config` package shadows scripts/config/ and the from-import raises.
    Calls the rebound `is_valid_project_root` to confirm the real implementation
    survived the cache eviction (a stale shadow would either raise on import or
    bind a placeholder that returns the wrong value).
    """
    reloaded_module = _reload_with_stale_config_cache(
        "grant_project_claude_permissions"
    )
    real_project_root = tmp_path / "project_root"
    (real_project_root / ".claude").mkdir(parents=True)
    bare_directory = tmp_path / "no_claude_marker"
    bare_directory.mkdir()
    assert reloaded_module.is_valid_project_root(real_project_root) is True
    assert reloaded_module.is_valid_project_root(bare_directory) is False


def test_revoke_module_import_evicts_cached_config_submodules(
    tmp_path: Path,
) -> None:
    """revoke_project_claude_permissions must evict cached `config.*` on import.

    Regression for loop1-3: without a defensive cache pop above sys.path.insert,
    a cached `config` package shadows scripts/config/ and the from-import raises.
    Calls the rebound `is_valid_project_root` to confirm the real implementation
    survived the cache eviction (a stale shadow would either raise on import or
    bind a placeholder that returns the wrong value).
    """
    reloaded_module = _reload_with_stale_config_cache(
        "revoke_project_claude_permissions"
    )
    real_project_root = tmp_path / "project_root"
    (real_project_root / ".claude").mkdir(parents=True)
    bare_directory = tmp_path / "no_claude_marker"
    bare_directory.mkdir()
    assert reloaded_module.is_valid_project_root(real_project_root) is True
    assert reloaded_module.is_valid_project_root(bare_directory) is False
