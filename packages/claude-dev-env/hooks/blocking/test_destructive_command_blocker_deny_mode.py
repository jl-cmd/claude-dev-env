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
DENY_MODE_ENV_VAR = "CLAUDE_DESTRUCTIVE_DENY_MODE"


def _run_hook_with_environment(command: str, extra_environment: dict[str, str]) -> dict:
    child_environment = os.environ.copy()
    child_environment.pop(DENY_MODE_ENV_VAR, None)
    child_environment.update(extra_environment)
    completed_process = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
    )
    return json.loads(completed_process.stdout)


def test_rm_rf_denies_when_deny_mode_env_is_set() -> None:
    response = _run_hook_with_environment("rm -rf /var/log/myapp", {DENY_MODE_ENV_VAR: "1"})
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "rm -rf" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_rm_rf_asks_when_deny_mode_env_is_absent() -> None:
    response = _run_hook_with_environment("rm -rf /var/log/myapp", {})
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "rm -rf" in response["hookSpecificOutput"]["permissionDecisionReason"]
