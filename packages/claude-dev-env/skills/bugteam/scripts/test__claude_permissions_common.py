"""TDD-pair tests for the underscore-prefixed _claude_permissions_common module.

The TDD enforcer matches a production filename ``X.py`` to ``test_X.py``;
``_claude_permissions_common.py`` carries a leading underscore that the
enforcer treats as part of the name. This file's tests are the canonical
match. The broader behavioral suite continues to live alongside, in
``test_claude_permissions_common.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

import _claude_permissions_common as common_module


def test_write_atomically_with_mode_releases_fd_when_fdopen_raises(
    tmp_path: Path,
) -> None:
    """A failure inside os.fdopen must close the raw file descriptor."""
    target_path = tmp_path / "settings.json.tmp"
    with patch.object(
        common_module.os, "fdopen", side_effect=MemoryError("fdopen failure")
    ):
        with pytest.raises(MemoryError):
            common_module.write_atomically_with_mode(
                target_path, "payload", file_mode=0o600
            )


def test_get_mode_to_preserve_returns_existing_file_mode(
    tmp_path: Path,
) -> None:
    """When the file exists, the actual filesystem mode must be returned (not the default)."""
    target_path = tmp_path / "settings.json"
    target_path.write_text("{}", encoding="utf-8")
    actual_filesystem_mode = target_path.stat().st_mode & 0o777
    returned_mode = common_module.get_mode_to_preserve(target_path)
    assert returned_mode == actual_filesystem_mode


def test_write_atomically_with_mode_raises_oserror_when_open_fails(
    tmp_path: Path,
) -> None:
    """OSError from os.open must propagate (no fd leak path to test here)."""
    target_path = tmp_path / "subdirectory" / "missing" / "settings.json.tmp"
    with pytest.raises(OSError):
        common_module.write_atomically_with_mode(
            target_path, "payload", file_mode=0o600
        )


def test_write_atomically_unlinks_temp_when_fdopen_raises(
    tmp_path: Path,
) -> None:
    """A failure inside os.fdopen must remove the on-disk temp file.

    Regression for loop1-9: the file existed the moment os.open returned,
    but the OSError/MemoryError handler only closed the raw FD — leaving an
    empty .tmp sibling on disk after the exception propagated up to
    save_settings, where the unlink in the finally block was skipped because
    `is_temp_owned_by_this_invocation` had not yet been set.
    """
    target_path = tmp_path / "settings.json.tmp"
    with patch.object(
        common_module.os, "fdopen", side_effect=MemoryError("fdopen failure")
    ):
        with pytest.raises(MemoryError):
            common_module.write_atomically_with_mode(
                target_path, "payload", file_mode=0o600
            )
    assert not target_path.exists(), (
        "the temp file created by os.open must be unlinked before re-raising"
    )


def test_save_settings_uses_pid_keyed_temp_suffix(tmp_path: Path) -> None:
    """Concurrent save_settings invocations must not race on a deterministic temp name.

    Regression for loop1-10: building the temp path as `settings.json.tmp` is
    deterministic and unkeyed by PID, so two parallel /bugteam invocations
    racing on Step 0 (grant) or Step 5 (revoke) collide on O_CREAT|O_EXCL —
    the second caller hits FileExistsError and the OSError handler hard-exits,
    silently dropping that PR's permission grant.
    """
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    captured_temp_paths: list[str] = []
    real_open = common_module.os.open

    def capturing_open(target: str, *args: object, **kwargs: object) -> int:
        captured_temp_paths.append(target)
        return real_open(target, *args, **kwargs)

    with patch.object(common_module.os, "open", side_effect=capturing_open):
        common_module.save_settings(settings_path, {"first": True})
        common_module.save_settings(settings_path, {"second": True})
    assert len(captured_temp_paths) == 2
    assert all(
        str(common_module.os.getpid()) in each_temp_path
        for each_temp_path in captured_temp_paths
    ), (
        "temp filename must include os.getpid() so concurrent runs do not "
        f"collide on a deterministic name; saw: {captured_temp_paths!r}"
    )
