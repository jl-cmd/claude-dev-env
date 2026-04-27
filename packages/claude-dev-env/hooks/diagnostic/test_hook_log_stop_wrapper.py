"""Tests for hook_log_stop_wrapper -- debounced, fire-and-forget Stop hook."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from diagnostic import hook_log_stop_wrapper
from config.hook_log_extractor_constants import (
    BWS_ACCESS_TOKEN_ENV_VAR,
    BWS_EXECUTABLE_NAME,
    FLAG_INCREMENTAL,
    STOP_WRAPPER_DEBOUNCE_SECONDS,
)


def _redirect_timestamp_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    timestamp_file = tmp_path / "stop_wrapper_last_run.txt"
    monkeypatch.setattr(
        hook_log_stop_wrapper,
        "_last_run_timestamp_path",
        lambda: timestamp_file,
    )
    return timestamp_file


def test_main_returns_zero_when_extractor_spawn_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timestamp_file = _redirect_timestamp_path(monkeypatch, tmp_path)
    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _raise)

    assert hook_log_stop_wrapper.main() == 0
    assert not timestamp_file.exists()


def test_main_writes_timestamp_before_spawn_to_narrow_toctou_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timestamp_file = _redirect_timestamp_path(monkeypatch, tmp_path)
    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    timestamp_file_existed_at_spawn_time: list[bool] = []

    def _capture_timestamp_state(*_args: object, **_kwargs: object) -> object:
        timestamp_file_existed_at_spawn_time.append(timestamp_file.exists())
        return object()

    monkeypatch.setattr(
        hook_log_stop_wrapper.subprocess, "Popen", _capture_timestamp_state
    )

    hook_log_stop_wrapper.main()

    assert timestamp_file_existed_at_spawn_time == [True]


def test_main_removes_timestamp_when_spawn_fails_to_allow_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timestamp_file = _redirect_timestamp_path(monkeypatch, tmp_path)
    timestamp_file.parent.mkdir(parents=True, exist_ok=True)
    stale_timestamp = time.time() - STOP_WRAPPER_DEBOUNCE_SECONDS - 1
    timestamp_file.write_text(str(stale_timestamp))

    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _raise)

    assert hook_log_stop_wrapper.main() == 0
    assert not timestamp_file.exists()


def test_main_uses_bws_when_token_and_binary_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_timestamp_path(monkeypatch, tmp_path)
    monkeypatch.setenv(BWS_ACCESS_TOKEN_ENV_VAR, "secret-value")
    monkeypatch.setattr(
        hook_log_stop_wrapper.shutil,
        "which",
        lambda _name: "/usr/local/bin/bws",
    )

    captured_commands: list[list[str]] = []

    def _fake_popen(command_list: list[str], **_kwargs: object) -> object:
        captured_commands.append(list(command_list))
        return object()

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _fake_popen)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 1
    assert captured_commands[0][0] == BWS_EXECUTABLE_NAME
    assert FLAG_INCREMENTAL in captured_commands[0]


def test_main_skips_bws_when_token_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_timestamp_path(monkeypatch, tmp_path)
    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(
        hook_log_stop_wrapper.shutil,
        "which",
        lambda _name: "/usr/local/bin/bws",
    )

    captured_commands: list[list[str]] = []

    def _fake_popen(command_list: list[str], **_kwargs: object) -> object:
        captured_commands.append(list(command_list))
        return object()

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _fake_popen)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 1
    assert BWS_EXECUTABLE_NAME not in captured_commands[0]


def test_main_skips_bws_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_timestamp_path(monkeypatch, tmp_path)
    monkeypatch.setenv(BWS_ACCESS_TOKEN_ENV_VAR, "secret-value")
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    captured_commands: list[list[str]] = []

    def _fake_popen(command_list: list[str], **_kwargs: object) -> object:
        captured_commands.append(list(command_list))
        return object()

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _fake_popen)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 1
    assert BWS_EXECUTABLE_NAME not in captured_commands[0]


def test_main_skips_spawn_when_recent_timestamp_within_debounce_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timestamp_file = _redirect_timestamp_path(monkeypatch, tmp_path)
    timestamp_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp_file.write_text(str(time.time()))

    captured_commands: list[list[str]] = []

    def _fake_popen(command_list: list[str], **_kwargs: object) -> object:
        captured_commands.append(list(command_list))
        return object()

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _fake_popen)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 0


def test_main_spawns_when_timestamp_older_than_debounce_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timestamp_file = _redirect_timestamp_path(monkeypatch, tmp_path)
    timestamp_file.parent.mkdir(parents=True, exist_ok=True)
    stale_timestamp = time.time() - STOP_WRAPPER_DEBOUNCE_SECONDS - 1
    timestamp_file.write_text(str(stale_timestamp))

    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    captured_commands: list[list[str]] = []

    def _fake_popen(command_list: list[str], **_kwargs: object) -> object:
        captured_commands.append(list(command_list))
        return object()

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _fake_popen)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 1


def test_main_writes_current_timestamp_after_spawn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timestamp_file = _redirect_timestamp_path(monkeypatch, tmp_path)
    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        hook_log_stop_wrapper.subprocess,
        "Popen",
        lambda *_args, **_kwargs: object(),
    )

    timestamp_before_call = time.time()
    hook_log_stop_wrapper.main()
    timestamp_after_call = time.time()

    assert timestamp_file.exists()
    written_timestamp = float(timestamp_file.read_text().strip())
    assert timestamp_before_call <= written_timestamp <= timestamp_after_call


def test_main_passes_devnull_streams_to_detached_spawn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_timestamp_path(monkeypatch, tmp_path)
    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    captured_kwargs: dict[str, object] = {}

    def _fake_popen(command_list: list[str], **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _fake_popen)

    hook_log_stop_wrapper.main()

    assert captured_kwargs.get("stdin") is hook_log_stop_wrapper.subprocess.DEVNULL
    assert captured_kwargs.get("stdout") is hook_log_stop_wrapper.subprocess.DEVNULL
    assert captured_kwargs.get("stderr") is hook_log_stop_wrapper.subprocess.DEVNULL


def test_main_recovers_when_timestamp_file_is_corrupted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timestamp_file = _redirect_timestamp_path(monkeypatch, tmp_path)
    timestamp_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp_file.write_text("not-a-float")

    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    captured_commands: list[list[str]] = []

    def _fake_popen(command_list: list[str], **_kwargs: object) -> object:
        captured_commands.append(list(command_list))
        return object()

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _fake_popen)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 1


def test_main_treats_future_timestamp_as_not_debounced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timestamp_file = _redirect_timestamp_path(monkeypatch, tmp_path)
    timestamp_file.parent.mkdir(parents=True, exist_ok=True)
    far_future_timestamp = time.time() + 3600
    timestamp_file.write_text(str(far_future_timestamp))

    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    captured_commands: list[list[str]] = []

    def _fake_popen(command_list: list[str], **_kwargs: object) -> object:
        captured_commands.append(list(command_list))
        return object()

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _fake_popen)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 1


def test_main_passes_hidden_startupinfo_on_windows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _redirect_timestamp_path(monkeypatch, tmp_path)
    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    captured_kwargs: dict[str, object] = {}

    def _fake_popen(command_list: list[str], **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "Popen", _fake_popen)

    hook_log_stop_wrapper.main()

    if os.name == "nt":
        startup_info = captured_kwargs.get("startupinfo")
        assert startup_info is not None
        assert startup_info.dwFlags & subprocess.STARTF_USESHOWWINDOW
        assert startup_info.wShowWindow == subprocess.SW_HIDE
    else:
        assert captured_kwargs.get("start_new_session") is True
