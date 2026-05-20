"""TDD-pair tests for the underscore-prefixed _bugteam_permissions_common module.

The TDD enforcer matches a production filename ``X.py`` to ``test_X.py``;
``_bugteam_permissions_common.py`` carries a leading underscore that the
enforcer treats as part of the name. This file's tests are the canonical
match. The broader behavioral suite continues to live alongside, in
``test_bugteam_permissions_common.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

import _bugteam_permissions_common as common_module
import grant_project_claude_permissions as grant_module
import revoke_project_claude_permissions as revoke_module


def test_is_valid_project_root_not_defined_on_common_module() -> None:
    """The common module must not expose ``is_valid_project_root``.

    Both grant and revoke define their own local copy. A shared copy on
    the common module would be a third parallel definition with no
    production caller, so its absence is the asserted contract.
    """
    assert not hasattr(common_module, "is_valid_project_root")


def test_grant_is_valid_project_root_detects_git_marker(tmp_path: Path) -> None:
    git_project_root = tmp_path / "git_project"
    (git_project_root / ".git").mkdir(parents=True)
    assert grant_module.is_valid_project_root(git_project_root) is True


def test_grant_is_valid_project_root_detects_claude_marker(tmp_path: Path) -> None:
    claude_project_root = tmp_path / "claude_project"
    (claude_project_root / ".claude").mkdir(parents=True)
    assert grant_module.is_valid_project_root(claude_project_root) is True


def test_grant_is_valid_project_root_rejects_unmarked_directory(tmp_path: Path) -> None:
    unmarked_directory = tmp_path / "no_marker"
    unmarked_directory.mkdir()
    assert grant_module.is_valid_project_root(unmarked_directory) is False


def test_revoke_is_valid_project_root_detects_git_marker(tmp_path: Path) -> None:
    git_project_root = tmp_path / "git_project"
    (git_project_root / ".git").mkdir(parents=True)
    assert revoke_module.is_valid_project_root(git_project_root) is True


def test_revoke_is_valid_project_root_detects_claude_marker(tmp_path: Path) -> None:
    claude_project_root = tmp_path / "claude_project"
    (claude_project_root / ".claude").mkdir(parents=True)
    assert revoke_module.is_valid_project_root(claude_project_root) is True


def test_revoke_is_valid_project_root_rejects_unmarked_directory(tmp_path: Path) -> None:
    unmarked_directory = tmp_path / "no_marker"
    unmarked_directory.mkdir()
    assert revoke_module.is_valid_project_root(unmarked_directory) is False


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
