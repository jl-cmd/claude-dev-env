"""Tests for the shared hidden-console creation flags."""

import pathlib
import subprocess
import sys
from typing import Any, Mapping

import pytest

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.subprocess_window import (
    detached_hidden_window_creation_flags,
    hidden_window_creation_flags,
    inherited_stream_startup_info,
)

WINDOWS_NO_WINDOW_FLAG = 0x08000000
WINDOWS_NEW_PROCESS_GROUP_FLAG = 0x00000200
WINDOWS_ONLY = pytest.mark.skipif(
    sys.platform != "win32", reason="subprocess.STARTUPINFO exists only on Windows"
)


def test_windows_reports_the_hidden_console_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", WINDOWS_NO_WINDOW_FLAG, raising=False)
    assert hidden_window_creation_flags() == WINDOWS_NO_WINDOW_FLAG


def test_other_platforms_report_no_creation_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert hidden_window_creation_flags() == 0


def test_windows_without_the_flag_attribute_reports_no_creation_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delattr(subprocess, "CREATE_NO_WINDOW", raising=False)
    assert hidden_window_creation_flags() == 0


def test_windows_detached_flags_add_a_new_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", WINDOWS_NO_WINDOW_FLAG, raising=False)
    monkeypatch.setattr(
        subprocess,
        "CREATE_NEW_PROCESS_GROUP",
        WINDOWS_NEW_PROCESS_GROUP_FLAG,
        raising=False,
    )
    assert detached_hidden_window_creation_flags() == (
        WINDOWS_NO_WINDOW_FLAG | WINDOWS_NEW_PROCESS_GROUP_FLAG
    )


def test_other_platforms_report_no_detached_creation_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert detached_hidden_window_creation_flags() == 0


def _captured_run_options(monkeypatch: pytest.MonkeyPatch) -> Mapping[str, Any]:
    """Run one command through a patched subprocess.run and return its options."""
    all_captured_options: dict[str, Any] = {}

    def fake_run(*_all_arguments: Any, **all_options: Any) -> None:
        all_captured_options.update(all_options)

    monkeypatch.setattr(subprocess, "run", fake_run)
    subprocess.run(
        ["git", "status"],
        creationflags=hidden_window_creation_flags(),
    )
    return all_captured_options


def test_a_call_site_passes_the_hidden_flag_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", WINDOWS_NO_WINDOW_FLAG, raising=False)
    assert _captured_run_options(monkeypatch)["creationflags"] == WINDOWS_NO_WINDOW_FLAG


def test_a_call_site_passes_the_default_flags_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert _captured_run_options(monkeypatch)["creationflags"] == 0


@WINDOWS_ONLY
def test_windows_startup_info_asks_for_a_hidden_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    startup_information = inherited_stream_startup_info()
    assert startup_information is not None
    assert startup_information.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert startup_information.wShowWindow == subprocess.SW_HIDE


def test_other_platforms_report_no_startup_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert inherited_stream_startup_info() is None


@WINDOWS_ONLY
def test_a_stream_inheriting_call_site_passes_no_creation_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_captured_options: dict[str, Any] = {}

    def fake_run(*_all_arguments: Any, **all_options: Any) -> None:
        all_captured_options.update(all_options)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", fake_run)
    subprocess.run(["python", "-m", "pytest"], startupinfo=inherited_stream_startup_info())
    assert "creationflags" not in all_captured_options
    assert all_captured_options["startupinfo"] is not None
