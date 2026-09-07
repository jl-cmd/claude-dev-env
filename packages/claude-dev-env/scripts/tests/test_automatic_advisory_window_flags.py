"""The advisory poller and every process it starts stay off the screen on Windows."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TESTS_DIRECTORY))

import test_automatic_advisory as support
from automatic_advisory import checkout, cli, execution, git, window_flags

WINDOWS_ONLY = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows console flags"
)
PROBE_WAIT_SECONDS = 10.0
PROBE_POLL_SECONDS = 0.1

CHILD_REPORT_SCRIPT = (
    "import ctypes, json, sys;"
    "handle = ctypes.windll.kernel32.GetConsoleWindow();"
    "visible = bool(ctypes.windll.user32.IsWindowVisible(handle)) if handle else False;"
    "sys.stdout.write(json.dumps({'visible': visible}))"
)

PARENT_PROBE_SCRIPT = """
import json, subprocess, sys
from pathlib import Path
completed = subprocess.run(
    [sys.executable, "-c", {child_script!r}], capture_output=True, text=True, check=False
)
Path(sys.argv[1]).write_text(completed.stdout, encoding="utf-8")
"""


def test_flags_are_zero_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(window_flags.sys, "platform", "linux")
    assert window_flags.hidden_window_creation_flags() == 0
    assert window_flags.detached_poller_creation_flags() == 0


@WINDOWS_ONLY
def test_hidden_window_creation_flags_is_create_no_window() -> None:
    assert window_flags.hidden_window_creation_flags() == subprocess.CREATE_NO_WINDOW


@WINDOWS_ONLY
def test_poller_flags_keep_a_hidden_console_instead_of_none() -> None:
    poller_flags = window_flags.detached_poller_creation_flags()
    assert poller_flags & subprocess.DETACHED_PROCESS == 0
    assert poller_flags & subprocess.CREATE_NO_WINDOW
    assert poller_flags & subprocess.CREATE_NEW_PROCESS_GROUP


@WINDOWS_ONLY
def test_poller_grandchild_gets_no_visible_console(tmp_path: Path) -> None:
    parent_script_path = tmp_path / "parent_probe.py"
    parent_script_path.write_text(
        PARENT_PROBE_SCRIPT.format(child_script=CHILD_REPORT_SCRIPT), encoding="utf-8"
    )
    report_path = tmp_path / "grandchild.json"
    subprocess.Popen(
        [sys.executable, str(parent_script_path), str(report_path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=window_flags.detached_poller_creation_flags(),
    )
    assert _read_probe_report(report_path) == {"visible": False}


def _read_probe_report(report_path: Path) -> dict[str, bool]:
    deadline = time.monotonic() + PROBE_WAIT_SECONDS
    while time.monotonic() < deadline:
        if report_path.exists():
            return json.loads(report_path.read_text(encoding="utf-8"))
        time.sleep(PROBE_POLL_SECONDS)
    raise AssertionError("the probe parent never wrote its report")


def test_git_fetch_hides_its_window(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registration = support._build_registration(tmp_path, tmp_path)
    candidate = support._build_candidate("head")
    captured_options: dict[str, object] = {}

    def record_run(
        *arguments: object, **options: object
    ) -> subprocess.CompletedProcess[bytes]:
        captured_options.update(options)
        return subprocess.CompletedProcess(arguments, 0, b"", b"")

    monkeypatch.setattr(git.subprocess, "run", record_run)

    assert git._fetch_base(registration, candidate) is True
    assert (
        captured_options["creationflags"] == window_flags.hidden_window_creation_flags()
    )


def test_checkout_inspection_hides_its_window(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_captured_flags: list[object] = []

    def record_run(
        *arguments: object, **options: object
    ) -> subprocess.CompletedProcess[str]:
        all_captured_flags.append(options["creationflags"])
        return subprocess.CompletedProcess(arguments, 0, "abc123\n", "")

    monkeypatch.setattr(checkout.subprocess, "run", record_run)

    local_checkout = checkout.read_local_checkout(tmp_path)

    assert local_checkout.head_sha == "abc123"
    assert all_captured_flags == [window_flags.hidden_window_creation_flags()] * 2


def test_windows_process_host_spawn_hides_its_window(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registration = support._build_registration(tmp_path, tmp_path)
    captured_options: dict[str, object] = {}

    def record_popen(*arguments: object, **options: object) -> object:
        captured_options.update(options)
        return object()

    monkeypatch.setattr(execution.subprocess, "Popen", record_popen)

    execution._spawn_windows_process_host(("python", "-c", "pass"), registration, {})

    expected_flags = window_flags.hidden_window_creation_flags() | getattr(
        subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0
    )
    assert captured_options["creationflags"] == expected_flags


def test_start_polling_launches_with_the_poller_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured_options: dict[str, object] = {}

    def record_popen(*arguments: object, **options: object) -> object:
        captured_options.update(options)
        return object()

    monkeypatch.setattr(cli.subprocess, "Popen", record_popen)

    assert cli.start_polling(tmp_path / "settings.json") == 0
    assert (
        captured_options["creationflags"]
        == window_flags.detached_poller_creation_flags()
    )
