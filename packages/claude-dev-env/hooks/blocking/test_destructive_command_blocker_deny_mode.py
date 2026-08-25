"""Tests for the destructive-command-blocker deny mode.

The sandbox runs under ``--dangerously-skip-permissions``, which auto-resolves
an ``ask`` decision, so only a hard ``deny`` contains a destructive command.
Setting ``CLAUDE_DESTRUCTIVE_DENY_MODE`` turns the hook's terminal ``ask`` into
a ``deny`` so the sandbox can be contained.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
if str(_BLOCKING_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIRECTORY))

SCRIPT_PATH = _BLOCKING_DIRECTORY / "destructive_command_blocker.py"
DISPATCHER_PATH = _BLOCKING_DIRECTORY / "bash_pre_tool_use_dispatcher.py"

import _path_setup  # noqa: E402, F401

from test_hook_subprocess_support import (  # noqa: E402
    build_bash_payload,
    run_hook_as_subprocess,
)


def _run_hook_with_environment(
    hook_script_path: Path,
    command: str,
    environment_update_by_name: dict[str, str],
    temporary_home_directory: Path,
) -> subprocess.CompletedProcess[str]:
    return run_hook_as_subprocess(
        hook_script_path=hook_script_path,
        payload_text=build_bash_payload(command),
        working_directory=temporary_home_directory,
        home_directory=temporary_home_directory,
        all_environment_names_to_remove=("CLAUDE_DESTRUCTIVE_DENY_MODE",),
        environment_updates_by_name=environment_update_by_name,
    )


def _assert_terminal_response(
    completed_hook: subprocess.CompletedProcess[str],
    expected_permission_decision: str,
    expected_permission_reason: str,
) -> None:
    assert completed_hook.returncode == 0
    assert completed_hook.stderr == ""
    assert json.loads(completed_hook.stdout) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": expected_permission_decision,
            "permissionDecisionReason": expected_permission_reason,
        }
    }


def test_rm_rf_denies_when_deny_mode_env_is_set(tmp_path: Path) -> None:
    completed_hook = _run_hook_with_environment(
        SCRIPT_PATH,
        "rm -rf /var/log/myapp",
        {"CLAUDE_DESTRUCTIVE_DENY_MODE": "1"},
        tmp_path,
    )
    _assert_terminal_response(
        completed_hook,
        "deny",
        "DESTRUCTIVE: rm -rf (destructive recursive forced delete). "
        "Blocked in deny mode.",
    )


def test_rm_rf_asks_when_deny_mode_env_is_absent(tmp_path: Path) -> None:
    completed_hook = _run_hook_with_environment(
        SCRIPT_PATH,
        "rm -rf /var/log/myapp",
        {},
        tmp_path,
    )
    _assert_terminal_response(
        completed_hook,
        "ask",
        "DESTRUCTIVE: rm -rf (destructive recursive forced delete). "
        "Requires explicit user approval.",
    )


def test_dispatcher_short_circuits_on_destructive_deny(tmp_path: Path) -> None:
    completed_dispatcher = _run_hook_with_environment(
        DISPATCHER_PATH,
        "rm -rf /var/log/myapp",
        {"CLAUDE_DESTRUCTIVE_DENY_MODE": "1"},
        tmp_path,
    )
    _assert_terminal_response(
        completed_dispatcher,
        "deny",
        "DESTRUCTIVE: rm -rf (destructive recursive forced delete). "
        "Blocked in deny mode.",
    )
