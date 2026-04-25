"""Tests for hook_log_stop_wrapper — Stop-hook wrapper that never fails."""

from __future__ import annotations

import sys
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
)


def test_main_returns_zero_when_bws_missing_and_extractor_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "run", _raise)

    assert hook_log_stop_wrapper.main() == 0


def test_main_uses_bws_when_token_and_binary_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(BWS_ACCESS_TOKEN_ENV_VAR, "secret-value")
    monkeypatch.setattr(
        hook_log_stop_wrapper.shutil,
        "which",
        lambda _name: "/usr/local/bin/bws",
    )

    captured_commands: list[list[str]] = []

    def _fake_run(command_list: list[str], **_kwargs: object) -> None:
        captured_commands.append(list(command_list))

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "run", _fake_run)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 1
    assert captured_commands[0][0] == BWS_EXECUTABLE_NAME
    assert FLAG_INCREMENTAL in captured_commands[0]


def test_main_skips_bws_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(BWS_ACCESS_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(
        hook_log_stop_wrapper.shutil,
        "which",
        lambda _name: "/usr/local/bin/bws",
    )

    captured_commands: list[list[str]] = []

    def _fake_run(command_list: list[str], **_kwargs: object) -> None:
        captured_commands.append(list(command_list))

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "run", _fake_run)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 1
    assert BWS_EXECUTABLE_NAME not in captured_commands[0]


def test_main_skips_bws_when_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(BWS_ACCESS_TOKEN_ENV_VAR, "secret-value")
    monkeypatch.setattr(hook_log_stop_wrapper.shutil, "which", lambda _name: None)

    captured_commands: list[list[str]] = []

    def _fake_run(command_list: list[str], **_kwargs: object) -> None:
        captured_commands.append(list(command_list))

    monkeypatch.setattr(hook_log_stop_wrapper.subprocess, "run", _fake_run)

    exit_code = hook_log_stop_wrapper.main()

    assert exit_code == 0
    assert len(captured_commands) == 1
    assert BWS_EXECUTABLE_NAME not in captured_commands[0]
