"""Tests for the destructive-command-blocker deny mode.

The sandbox runs under ``--dangerously-skip-permissions``, which auto-resolves
an ``ask`` decision, so only a hard ``deny`` contains a destructive command.
Setting ``CLAUDE_DESTRUCTIVE_DENY_MODE`` turns the hook's terminal ``ask`` into
a ``deny`` so the sandbox can be contained.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent / "destructive_command_blocker.py"
DISPATCHER_PATH = Path(__file__).parent / "bash_pre_tool_use_dispatcher.py"
DENY_MODE_ENV_VAR = "CLAUDE_DESTRUCTIVE_DENY_MODE"


def _run_hook_with_environment(
    command: str,
    extra_environment: dict[str, str],
    script_path: Path = SCRIPT_PATH,
) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    child_environment.pop(DENY_MODE_ENV_VAR, None)
    child_environment.update(extra_environment)
    return subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
    )


def _assert_terminal_response(
    completed_hook: subprocess.CompletedProcess[str],
    expected_decision: str,
    expected_reason: str,
) -> None:
    assert completed_hook.returncode == 0
    assert completed_hook.stderr == ""
    assert json.loads(completed_hook.stdout) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": expected_decision,
            "permissionDecisionReason": expected_reason,
        }
    }


def test_rm_rf_denies_when_deny_mode_env_is_set() -> None:
    completed_hook = _run_hook_with_environment(
        "rm -rf /var/log/myapp",
        {DENY_MODE_ENV_VAR: "1"},
    )

    _assert_terminal_response(
        completed_hook,
        "deny",
        "DESTRUCTIVE: rm -rf (destructive recursive forced delete). "
        "Blocked in deny mode.",
    )


def test_rm_rf_asks_when_deny_mode_env_is_absent() -> None:
    completed_hook = _run_hook_with_environment("rm -rf /var/log/myapp", {})

    _assert_terminal_response(
        completed_hook,
        "ask",
        "DESTRUCTIVE: rm -rf (destructive recursive forced delete). "
        "Requires explicit user approval.",
    )


def test_dispatcher_short_circuits_on_destructive_deny() -> None:
    completed_dispatcher = _run_hook_with_environment(
        "rm -rf /var/log/myapp",
        {DENY_MODE_ENV_VAR: "1"},
        DISPATCHER_PATH,
    )

    _assert_terminal_response(
        completed_dispatcher,
        "deny",
        "DESTRUCTIVE: rm -rf (destructive recursive forced delete). "
        "Blocked in deny mode.",
    )
