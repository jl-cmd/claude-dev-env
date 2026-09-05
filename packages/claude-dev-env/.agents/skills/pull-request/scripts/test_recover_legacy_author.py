"""Contract tests for explicit legacy GitHub author recovery."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

import recover_legacy_author

CURRENT_TIME_SECONDS = 2_000_000.0
CURRENT_USER_ID = 41
LEGACY_ACCOUNT = "previous-account"
OTHER_ACCOUNT = "other-account"
STATE_FILENAME = "gh_pr_author_swap_session-a.json"


def _completion(
    code: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout, stderr)


def _write_state(
    directory: Path,
    *,
    filename: str = STATE_FILENAME,
    payload: object | None = None,
    age_seconds: float = 1801.0,
) -> Path:
    state_file = directory / filename
    state_payload = {"original_account": LEGACY_ACCOUNT} if payload is None else payload
    state_file.write_text(json.dumps(state_payload), encoding="utf-8")
    os.utime(
        state_file,
        (CURRENT_TIME_SECONDS - age_seconds, CURRENT_TIME_SECONDS - age_seconds),
    )
    if hasattr(os, "getuid"):
        state_file.chmod(0o600)
    return state_file


def _run(
    state_file: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]],
    *,
    confirm_inactive: bool = True,
) -> int:
    all_arguments = [str(state_file)]
    if confirm_inactive:
        all_arguments.append("--confirm-inactive")
    return recover_legacy_author.main(
        all_arguments,
        now_seconds=CURRENT_TIME_SECONDS,
        current_user_id=os.getuid() if hasattr(os, "getuid") else None,
        command_runner=command_runner,
    )


def test_success_restores_selected_record_and_preserves_neighbor(
    tmp_path: Path,
) -> None:
    selected_file = _write_state(tmp_path)
    neighbor_file = _write_state(
        tmp_path,
        filename="gh_pr_author_swap_session-b.json",
        payload={"original_account": OTHER_ACCOUNT},
    )
    command_runner = Mock(return_value=_completion())
    assert _run(selected_file, command_runner) == 0
    command_runner.assert_called_once_with(
        ["gh", "auth", "switch", "--user", LEGACY_ACCOUNT],
        capture_output=True,
        check=False,
        shell=False,
        text=True,
    )
    assert not selected_file.exists()
    assert neighbor_file.exists()


def test_unconfirmed_record_is_unresolved_without_side_effects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state_file = _write_state(tmp_path)
    command_runner = Mock()
    assert _run(state_file, command_runner, confirm_inactive=False) == 3
    assert "confirm inactive" in capsys.readouterr().err
    command_runner.assert_not_called()
    assert state_file.exists()


def test_active_record_is_rejected_without_side_effects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state_file = _write_state(tmp_path, age_seconds=10.0)
    command_runner = Mock()
    assert _run(state_file, command_runner) == 2
    assert "record is active" in capsys.readouterr().err
    command_runner.assert_not_called()
    assert state_file.exists()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"original_account": ""},
        {"original_account": 7},
        {"original_account": LEGACY_ACCOUNT, "extra": True},
    ],
)
def test_invalid_schema_is_rejected(
    tmp_path: Path, payload: object, capsys: pytest.CaptureFixture[str]
) -> None:
    state_file = _write_state(tmp_path, payload=payload)
    command_runner = Mock()
    assert _run(state_file, command_runner) == 2
    assert "record is invalid" in capsys.readouterr().err
    command_runner.assert_not_called()
    assert state_file.exists()


def test_invalid_utf8_is_rejected(tmp_path: Path) -> None:
    state_file = _write_state(tmp_path)
    state_file.write_bytes(b"\xff")
    os.utime(state_file, (CURRENT_TIME_SECONDS - 1801, CURRENT_TIME_SECONDS - 1801))
    command_runner = Mock()
    assert _run(state_file, command_runner) == 2
    command_runner.assert_not_called()
    assert state_file.exists()


def test_wrong_filename_is_rejected(tmp_path: Path) -> None:
    state_file = _write_state(tmp_path, filename="other.json")
    command_runner = Mock()
    assert _run(state_file, command_runner) == 2
    command_runner.assert_not_called()


def test_symlink_is_rejected(tmp_path: Path) -> None:
    target_file = _write_state(tmp_path)
    link_file = tmp_path / "gh_pr_author_swap_link.json"
    try:
        link_file.symlink_to(target_file)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")
    command_runner = Mock()
    assert _run(link_file, command_runner) == 2
    command_runner.assert_not_called()
    assert target_file.exists()


def test_failed_restore_preserves_record_and_hides_child_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state_file = _write_state(tmp_path)
    command_runner = Mock(
        return_value=_completion(1, LEGACY_ACCOUNT, f"unsafe {LEGACY_ACCOUNT}")
    )
    assert _run(state_file, command_runner) == 1
    captured = capsys.readouterr()
    assert captured.err == "error: GitHub account restore failed\n"
    assert LEGACY_ACCOUNT not in captured.out + captured.err
    assert state_file.exists()


def test_restore_launch_failure_preserves_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state_file = _write_state(tmp_path)
    command_runner = Mock(side_effect=OSError("unavailable"))
    assert _run(state_file, command_runner) == 1
    assert capsys.readouterr().err == "error: GitHub account restore failed\n"
    assert state_file.exists()


def test_changed_record_after_restore_is_preserved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state_file = _write_state(tmp_path)

    def change_record(
        all_arguments: list[str], **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        state_file.write_text(
            json.dumps({"original_account": OTHER_ACCOUNT}), encoding="utf-8"
        )
        return _completion()

    assert _run(state_file, change_record) == 1
    assert "record changed" in capsys.readouterr().err
    assert state_file.exists()


def test_secure_posix_metadata_requires_regular_owner_mode() -> None:
    regular_secure_mode = stat.S_IFREG | 0o600
    assert recover_legacy_author._posix_metadata_is_secure(
        regular_secure_mode, CURRENT_USER_ID, CURRENT_USER_ID
    )
    assert not recover_legacy_author._posix_metadata_is_secure(
        regular_secure_mode, CURRENT_USER_ID + 1, CURRENT_USER_ID
    )
    assert not recover_legacy_author._posix_metadata_is_secure(
        stat.S_IFREG | 0o644, CURRENT_USER_ID, CURRENT_USER_ID
    )
    assert not recover_legacy_author._posix_metadata_is_secure(
        stat.S_IFLNK | 0o600, CURRENT_USER_ID, CURRENT_USER_ID
    )
