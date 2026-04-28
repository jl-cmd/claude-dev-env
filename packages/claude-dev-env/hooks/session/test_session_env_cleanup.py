"""Tests for session_env_cleanup — SessionStart hook for Bash EEXIST workaround."""

from __future__ import annotations

import io
import json
import os
import stat
import sys
import time
from pathlib import Path
from unittest.mock import patch

_SESSION_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _SESSION_DIR.parent
for each_sys_path_entry in (str(_SESSION_DIR), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

import session_env_cleanup as cleanup

SECONDS_PER_DAY = 24 * 60 * 60
SEVEN_DAYS_IN_SECONDS = 7 * SECONDS_PER_DAY


def _set_mtime_days_ago(target_path: Path, days_ago: float) -> None:
    target_mtime_seconds = time.time() - (days_ago * SECONDS_PER_DAY)
    os.utime(target_path, (target_mtime_seconds, target_mtime_seconds))


class TestRemovesCurrentSessionDirectory:
    def test_removes_directory_matching_session_id(self, tmp_path: Path) -> None:
        current_session_id = "abc-123"
        current_session_directory = tmp_path / current_session_id
        current_session_directory.mkdir()
        cleanup.prune_session_env(
            session_env_directory=str(tmp_path),
            session_id=current_session_id,
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert not current_session_directory.exists()

    def test_removes_current_session_directory_with_contents(
        self, tmp_path: Path
    ) -> None:
        current_session_id = "abc-123"
        current_session_directory = tmp_path / current_session_id
        current_session_directory.mkdir()
        (current_session_directory / "leftover.txt").write_text("data")
        cleanup.prune_session_env(
            session_env_directory=str(tmp_path),
            session_id=current_session_id,
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert not current_session_directory.exists()

    def test_no_current_session_removal_when_session_id_empty(
        self, tmp_path: Path
    ) -> None:
        sibling_directory = tmp_path / "some-other-session"
        sibling_directory.mkdir()
        _set_mtime_days_ago(sibling_directory, days_ago=0)
        cleanup.prune_session_env(
            session_env_directory=str(tmp_path),
            session_id="",
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert sibling_directory.exists()


class TestPrunesStaleEntries:
    def test_removes_entry_older_than_threshold(self, tmp_path: Path) -> None:
        stale_directory = tmp_path / "old-session"
        stale_directory.mkdir()
        _set_mtime_days_ago(stale_directory, days_ago=10)
        cleanup.prune_session_env(
            session_env_directory=str(tmp_path),
            session_id="",
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert not stale_directory.exists()

    def test_keeps_entry_within_threshold(self, tmp_path: Path) -> None:
        fresh_directory = tmp_path / "fresh-session"
        fresh_directory.mkdir()
        _set_mtime_days_ago(fresh_directory, days_ago=2)
        cleanup.prune_session_env(
            session_env_directory=str(tmp_path),
            session_id="",
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert fresh_directory.exists()

    def test_removes_stale_directory_with_contents(self, tmp_path: Path) -> None:
        stale_directory = tmp_path / "stale-with-content"
        stale_directory.mkdir()
        (stale_directory / "leftover.txt").write_text("old data")
        _set_mtime_days_ago(stale_directory, days_ago=14)
        cleanup.prune_session_env(
            session_env_directory=str(tmp_path),
            session_id="",
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert not stale_directory.exists()

    def test_keeps_fresh_when_pruning_among_mixed_ages(self, tmp_path: Path) -> None:
        fresh_directory = tmp_path / "fresh-keep"
        stale_directory = tmp_path / "stale-remove"
        fresh_directory.mkdir()
        stale_directory.mkdir()
        _set_mtime_days_ago(fresh_directory, days_ago=1)
        _set_mtime_days_ago(stale_directory, days_ago=30)
        cleanup.prune_session_env(
            session_env_directory=str(tmp_path),
            session_id="",
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert fresh_directory.exists()
        assert not stale_directory.exists()


class TestRemovesReadOnlyDirectories:
    def test_removes_session_directory_with_read_only_contents(
        self, tmp_path: Path
    ) -> None:
        current_session_id = "readonly-session"
        current_session_directory = tmp_path / current_session_id
        current_session_directory.mkdir()
        leftover_file = current_session_directory / "leftover.txt"
        leftover_file.write_text("data")
        leftover_file.chmod(stat.S_IREAD)
        cleanup.prune_session_env(
            session_env_directory=str(tmp_path),
            session_id=current_session_id,
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert not current_session_directory.exists()

    def test_prunes_stale_directory_with_read_only_contents(
        self, tmp_path: Path
    ) -> None:
        stale_directory = tmp_path / "stale-readonly"
        stale_directory.mkdir()
        stale_file = stale_directory / "old.txt"
        stale_file.write_text("old data")
        stale_file.chmod(stat.S_IREAD)
        _set_mtime_days_ago(stale_directory, days_ago=14)
        cleanup.prune_session_env(
            session_env_directory=str(tmp_path),
            session_id="",
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert not stale_directory.exists()


class TestParentDirectoryMissing:
    def test_returns_silently_when_parent_missing(self, tmp_path: Path) -> None:
        absent_path = tmp_path / "does-not-exist"
        cleanup.prune_session_env(
            session_env_directory=str(absent_path),
            session_id="abc-123",
            stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
        )
        assert not absent_path.exists()


class TestMainReadsSessionIdFromStdin:
    def test_main_invokes_prune_with_stdin_session_id(self, tmp_path: Path) -> None:
        captured_call = {}

        def fake_prune(
            session_env_directory: str,
            session_id: str,
            stale_age_seconds: float,
        ) -> None:
            captured_call["session_id"] = session_id

        stdin_payload = io.StringIO(json.dumps({"session_id": "session-from-stdin"}))
        with (
            patch.object(cleanup, "prune_session_env", side_effect=fake_prune),
            patch("sys.stdin", stdin_payload),
        ):
            cleanup.main()
        assert captured_call["session_id"] == "session-from-stdin"

    def test_main_passes_empty_session_id_when_stdin_invalid(self) -> None:
        captured_call = {}

        def fake_prune(
            session_env_directory: str,
            session_id: str,
            stale_age_seconds: float,
        ) -> None:
            captured_call["session_id"] = session_id

        stdin_payload = io.StringIO("not json at all")
        with (
            patch.object(cleanup, "prune_session_env", side_effect=fake_prune),
            patch("sys.stdin", stdin_payload),
        ):
            cleanup.main()
        assert captured_call["session_id"] == ""

    def test_main_rejects_session_id_with_path_separator(self) -> None:
        captured_call = {}

        def fake_prune(
            session_env_directory: str,
            session_id: str,
            stale_age_seconds: float,
        ) -> None:
            captured_call["session_id"] = session_id

        stdin_payload = io.StringIO(json.dumps({"session_id": "../../../etc/passwd"}))
        with (
            patch.object(cleanup, "prune_session_env", side_effect=fake_prune),
            patch("sys.stdin", stdin_payload),
            patch.object(cleanup.sys, "platform", "win32"),
        ):
            cleanup.main()
        assert captured_call["session_id"] == ""

    def test_main_rejects_absolute_windows_path_session_id(self) -> None:
        captured_call = {}

        def fake_prune(
            session_env_directory: str,
            session_id: str,
            stale_age_seconds: float,
        ) -> None:
            captured_call["session_id"] = session_id

        stdin_payload = io.StringIO(json.dumps({"session_id": "C:\\Windows\\Temp"}))
        with (
            patch.object(cleanup, "prune_session_env", side_effect=fake_prune),
            patch("sys.stdin", stdin_payload),
            patch.object(cleanup.sys, "platform", "win32"),
        ):
            cleanup.main()
        assert captured_call["session_id"] == ""


class TestMainPlatformGuard:
    def test_main_no_ops_on_non_windows(self) -> None:
        captured_call = {"called": False}

        def fake_prune(
            session_env_directory: str,
            session_id: str,
            stale_age_seconds: float,
        ) -> None:
            captured_call["called"] = True

        stdin_payload = io.StringIO(json.dumps({"session_id": "abc-123"}))
        with (
            patch.object(cleanup, "prune_session_env", side_effect=fake_prune),
            patch("sys.stdin", stdin_payload),
            patch.object(cleanup.sys, "platform", "linux"),
        ):
            cleanup.main()
        assert captured_call["called"] is False


class TestPruneHandlesListdirFailure:
    def test_prune_returns_silently_when_listdir_raises(self, tmp_path: Path) -> None:
        existing_session_directory = tmp_path / "still-there"
        existing_session_directory.mkdir()

        def raise_oserror(path: str) -> list[str]:
            raise OSError("simulated listdir failure")

        with patch("os.listdir", side_effect=raise_oserror):
            cleanup.prune_session_env(
                session_env_directory=str(tmp_path),
                session_id="",
                stale_age_seconds=SEVEN_DAYS_IN_SECONDS,
            )
        assert existing_session_directory.exists()
