"""Regression tests for the leading-underscore _claude_permissions_common module.

The companion test_claude_permissions_common.py covers the public-name
matched suite. This file holds tests the TDD enforcer pairs to the
leading-underscore production filename.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_common_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "_claude_permissions_common.py"
    parent_directory = str(module_path.parent.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    spec = importlib.util.spec_from_file_location(
        "_claude_permissions_common", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _load_common_module()


def test_save_settings_chmods_after_replace_to_defeat_umask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: POSIX umask masks the mode passed to os.open, so the
    "preserve mode" intent is silently defeated unless save_settings
    chmods the final file after os.replace.
    """
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({}), encoding="utf-8")
    captured_mode_to_preserve = 0o600
    monkeypatch.setattr(
        common, "get_mode_to_preserve", lambda _path: captured_mode_to_preserve
    )

    ordered_calls: list[tuple[str, str, int | None]] = []
    real_replace = common.os.replace
    real_chmod = common.os.chmod

    def recording_replace(source_path: str, destination_path: str) -> None:
        ordered_calls.append(("replace", str(destination_path), None))
        real_replace(source_path, destination_path)

    def recording_chmod(target_path: str, file_mode: int) -> None:
        ordered_calls.append(("chmod", str(target_path), file_mode))
        real_chmod(target_path, file_mode)

    monkeypatch.setattr(common.os, "replace", recording_replace)
    monkeypatch.setattr(common.os, "chmod", recording_chmod)

    common.save_settings(settings_path, {"writer": "only"})

    final_replace_index = next(
        each_index
        for each_index, each_call in enumerate(ordered_calls)
        if each_call[0] == "replace" and each_call[1] == str(settings_path)
    )
    final_chmod_index = next(
        (
            each_index
            for each_index, each_call in enumerate(ordered_calls)
            if each_call[0] == "chmod"
            and each_call[1] == str(settings_path)
            and each_call[2] == captured_mode_to_preserve
        ),
        None,
    )
    assert final_chmod_index is not None
    assert final_replace_index < final_chmod_index


def test_path_contains_glob_metacharacters_rejects_true_metacharacters() -> None:
    assert common.path_contains_glob_metacharacters("C:/some/path/*.py") is True
    assert common.path_contains_glob_metacharacters("C:/some/path/[abc].py") is True
    assert common.path_contains_glob_metacharacters("C:/some/{a,b}/file") is True




def test_write_atomically_with_mode_closes_descriptor_when_fdopen_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: if os.fdopen fails, the raw descriptor from os.open must close.

    Cursor Bugbot: without a failure path, the descriptor
    leaks when fdopen raises before the file object assumes ownership.
    """
    closed_descriptors: list[int] = []
    sentinel_descriptor = 91

    def fake_open(_path: str, _flags: int, _mode: int = 0o777) -> int:
        return sentinel_descriptor

    def fake_fdopen(_file_descriptor: int, *_args: object, **_kwargs: object) -> object:
        raise OSError("simulated fdopen failure")

    def recording_close(file_descriptor: int) -> None:
        closed_descriptors.append(file_descriptor)

    monkeypatch.setattr(common.os, "open", fake_open)
    monkeypatch.setattr(common.os, "fdopen", fake_fdopen)
    monkeypatch.setattr(common.os, "close", recording_close)

    temporary_path = tmp_path / "tempfile.tmp"
    with pytest.raises(OSError, match="simulated fdopen failure"):
        common.write_atomically_with_mode(temporary_path, "{}", 0o600)

    assert closed_descriptors == [sentinel_descriptor]


def test_path_contains_glob_metacharacters_accepts_windows_paths_with_parens() -> None:
    """Regression: Windows paths like C:/Program Files (x86)/ must not raise ValueError.

    `(`, `)`, and `,` are not glob metacharacters in Claude Code's permission
    rule matching. Including them in the metacharacter set causes
    get_current_project_path to raise ValueError for any user whose home
    directory contains parentheses (e.g. `C:/Users/Jon (Admin)/...`).
    """
    assert common.path_contains_glob_metacharacters("C:/Program Files (x86)/app") is False
    assert common.path_contains_glob_metacharacters("C:/Users/Jon (Admin)/project") is False
    assert common.path_contains_glob_metacharacters("C:/Projects/a,b/file.py") is False

