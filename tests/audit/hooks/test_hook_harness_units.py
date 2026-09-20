"""Unit behavior for the harness helpers that start a hook and age a path.

::

    resolve_shell()                       -> an executable POSIX shell path
    run_hook(control_blocker, "forbidden-op --force")
        ok:   outcome "block"
        flag: outcome "silent" on a command the fixture allows
    age_path(probe, 3.0)                  -> modification time 3 days earlier
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from hook_harness import Sandbox, age_path, load_registrations, resolve_shell, run_hook

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
ALL_FIXTURE_REGISTRATIONS = load_registrations(FIXTURE_ROOT / "hooks" / "hooks.json")
SECONDS_PER_DAY = 86400.0
AGED_DAYS = 3.0
AGED_TOLERANCE_SECONDS = 120.0
FORBIDDEN_COMMAND = "forbidden-op --force"
ALLOWED_COMMAND = "ls -la"


def _control_run(command: str, tmp_path: Path) -> object:
    registration = next(
        each_registration
        for each_registration in ALL_FIXTURE_REGISTRATIONS
        if each_registration.hook_id.endswith("control_blocker.py")
    )
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
    )
    return run_hook(registration, payload, FIXTURE_ROOT, Sandbox(root=tmp_path))


def test_resolve_shell_names_an_executable_shell() -> None:
    shell_path = resolve_shell()

    assert os.access(shell_path, os.X_OK)


def test_age_path_moves_the_modification_time_back(tmp_path: Path) -> None:
    probe_path = tmp_path / "aged_probe.txt"
    probe_path.write_text("probe\n", encoding="utf-8")
    before_seconds = probe_path.stat().st_mtime

    age_path(probe_path, AGED_DAYS)

    moved_seconds = before_seconds - probe_path.stat().st_mtime
    assert abs(moved_seconds - AGED_DAYS * SECONDS_PER_DAY) < AGED_TOLERANCE_SECONDS


def test_run_hook_reports_the_block_a_refusing_hook_writes(tmp_path: Path) -> None:
    hook_run = _control_run(FORBIDDEN_COMMAND, tmp_path)

    assert hook_run.outcome == "block"
    assert FORBIDDEN_COMMAND in hook_run.stdout


def test_run_hook_stays_silent_on_a_command_the_hook_allows(tmp_path: Path) -> None:
    hook_run = _control_run(ALLOWED_COMMAND, tmp_path)

    assert hook_run.outcome == "silent"
    assert hook_run.stdout == ""
